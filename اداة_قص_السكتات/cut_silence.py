# -*- coding: utf-8 -*-
"""
أداة قص السكتات التلقائي
تاخد فيديو، تكتشف السكتات (الأجزاء اللي مفيهاش كلام) في الصوت،
وتطلعلك ملف XML تفتحه في Premiere Pro فتلاقي الفيديو متقطع
ومشال منه السكتات أوتوماتيك (على شكل تايم لاين فيه لقطات متتالية).

الأداة لا تعدل الفيديو الأصلي ولا تصدّر فيديو جديد - هي بس بتحلل
الصوت وتطلع "خريطة قص" على هيئة XML قياسي (XMEML) بريمير بيفهمه.
"""

import os
import re
import sys
import threading
import subprocess
from urllib.parse import quote

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


# ---------------------------------------------------------------------------
# تحليل الفيديو باستخدام ffmpeg (silencedetect)
# ---------------------------------------------------------------------------

DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
VIDEO_STREAM_RE = re.compile(
    r"Stream #\d+:\d+.*?Video:.*?,\s*(\d+)x(\d+)[^,]*?,.*?([\d.]+)\s*fps"
)
AUDIO_STREAM_RE = re.compile(
    r"Stream #\d+:\d+.*?Audio:.*?(\d+)\s*Hz,\s*(\w+)"
)
SILENCE_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)\s*\|\s*silence_duration:\s*(-?[\d.]+)")
TIME_PROGRESS_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def get_ffmpeg_path():
    if imageio_ffmpeg is None:
        raise RuntimeError("مكتبة imageio-ffmpeg غير مثبتة")
    return imageio_ffmpeg.get_ffmpeg_exe()


def hhmmss_to_seconds(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def analyze_video(video_path, noise_db, min_silence_sec, on_progress=None):
    """يشغل ffmpeg لتحليل الصوت فقط ويرجع معلومات الفيديو + السكتات المكتشفة."""
    ffmpeg = get_ffmpeg_path()

    cmd = [
        ffmpeg,
        "-i", video_path,
        "-vn",
        "-map", "0:a:0",
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_sec}",
        "-f", "null",
        "-",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
    )

    duration = None
    fps = None
    width = height = None
    audio_rate = 48000
    audio_channels = 2
    silences = []
    pending_start = None
    full_log = []

    for line in process.stderr:
        full_log.append(line)

        if duration is None:
            m = DURATION_RE.search(line)
            if m:
                duration = hhmmss_to_seconds(*m.groups())

        if fps is None:
            m = VIDEO_STREAM_RE.search(line)
            if m:
                width, height = int(m.group(1)), int(m.group(2))
                fps = float(m.group(3))

        m = AUDIO_STREAM_RE.search(line)
        if m:
            audio_rate = int(m.group(1))
            layout = m.group(2).lower()
            audio_channels = 1 if "mono" in layout else 2

        m = SILENCE_START_RE.search(line)
        if m:
            pending_start = float(m.group(1))

        m = SILENCE_END_RE.search(line)
        if m:
            end_t = float(m.group(1))
            start_t = pending_start if pending_start is not None else max(0.0, end_t - float(m.group(2)))
            silences.append((max(0.0, start_t), end_t))
            pending_start = None

        if on_progress and duration:
            m = TIME_PROGRESS_RE.search(line)
            if m:
                cur = hhmmss_to_seconds(*m.groups())
                on_progress(min(1.0, cur / duration))

    process.wait()

    if pending_start is not None and duration is not None and pending_start < duration:
        silences.append((pending_start, duration))

    if duration is None:
        raise RuntimeError("مقدرتش أقرا مدة الفيديو. اتأكد إن الملف سليم.\n\n" + "".join(full_log[-15:]))

    if fps is None:
        raise RuntimeError("مقدرتش ألاقي معلومات الفيديو (الفريم ريت). اتأكد إن الملف فيديو سليم.")

    return {
        "duration": duration,
        "fps": fps,
        "width": width,
        "height": height,
        "audio_rate": audio_rate,
        "audio_channels": audio_channels,
        "silences": silences,
    }


# ---------------------------------------------------------------------------
# حساب الأجزاء اللي هتفضل (الكلام) بعد ما نشيل السكتات
# ---------------------------------------------------------------------------

def compute_keep_segments(duration, silences, padding_sec, min_keep_sec):
    """يرجع لستة من (بداية، نهاية) بالثواني لللقطات اللي هتفضل بعد شيل السكتات."""
    # نقلل كل سكتة شوية من الطرفين (padding) عشان منقصش أول/آخر كلمة
    trimmed = []
    for s, e in silences:
        s2 = s + padding_sec
        e2 = e - padding_sec
        if e2 > s2:
            trimmed.append((s2, e2))

    trimmed.sort()

    keep = []
    cursor = 0.0
    for s, e in trimmed:
        if s > cursor:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration:
        keep.append((cursor, duration))

    # نشيل القطع الصغيرة جدًا (أقل من الحد الأدنى) عشان منعملش قصات كتير فارغة معنى
    keep = [(s, e) for s, e in keep if (e - s) >= min_keep_sec]

    return keep


# ---------------------------------------------------------------------------
# توليد XML بصيغة XMEML (اللي بريمير بيستوردها)
# ---------------------------------------------------------------------------

def to_pathurl(path):
    p = os.path.abspath(path).replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + "%3A" + p[2:]
    return "file://localhost/" + quote(p, safe="/%")


def detect_rate(fps):
    """يرجع (timebase صحيح, ntsc bool) مناسبين لفريم ريت الفيديو."""
    rounded = round(fps)
    if abs(fps - rounded) > 0.01:
        return rounded, True
    return rounded, False


def seconds_to_frames(t, timebase, ntsc):
    actual_fps = timebase * 1000.0 / 1001.0 if ntsc else float(timebase)
    return int(round(t * actual_fps))


def build_xmeml(video_path, keep_segments, info, sequence_name):
    timebase, ntsc = detect_rate(info["fps"])
    ntsc_str = "TRUE" if ntsc else "FALSE"

    name = os.path.basename(video_path)
    pathurl = to_pathurl(video_path)
    src_total_frames = seconds_to_frames(info["duration"], timebase, ntsc)
    width = info["width"] or 1920
    height = info["height"] or 1080

    video_clips = []
    audio_clips = []
    timeline_cursor = 0

    for i, (s, e) in enumerate(keep_segments):
        in_f = seconds_to_frames(s, timebase, ntsc)
        out_f = seconds_to_frames(e, timebase, ntsc)
        clip_len = out_f - in_f
        if clip_len <= 0:
            continue
        start_f = timeline_cursor
        end_f = timeline_cursor + clip_len
        timeline_cursor = end_f

        vid_id = f"clipitem-{2 * i + 1}"
        aud_id = f"clipitem-{2 * i + 2}"

        if i == 0:
            file_def = f"""<file id="file-1">
          <name>{escape_xml(name)}</name>
          <pathurl>{escape_xml(pathurl)}</pathurl>
          <rate>
            <timebase>{timebase}</timebase>
            <ntsc>{ntsc_str}</ntsc>
          </rate>
          <duration>{src_total_frames}</duration>
          <media>
            <video>
              <samplecharacteristics>
                <width>{width}</width>
                <height>{height}</height>
              </samplecharacteristics>
            </video>
            <audio>
              <samplecharacteristics>
                <depth>16</depth>
                <samplerate>{info["audio_rate"]}</samplerate>
              </samplecharacteristics>
              <channelcount>{info["audio_channels"]}</channelcount>
            </audio>
          </media>
        </file>"""
        else:
            file_def = '<file id="file-1"/>'

        video_clips.append(f"""      <clipitem id="{vid_id}">
        <name>{escape_xml(name)}</name>
        <duration>{src_total_frames}</duration>
        <rate>
          <timebase>{timebase}</timebase>
          <ntsc>{ntsc_str}</ntsc>
        </rate>
        <start>{start_f}</start>
        <end>{end_f}</end>
        <in>{in_f}</in>
        <out>{out_f}</out>
        {file_def}
        <link>
          <linkclipref>{vid_id}</linkclipref>
          <mediatype>video</mediatype>
          <trackindex>1</trackindex>
          <clipindex>{i + 1}</clipindex>
        </link>
        <link>
          <linkclipref>{aud_id}</linkclipref>
          <mediatype>audio</mediatype>
          <trackindex>1</trackindex>
          <clipindex>{i + 1}</clipindex>
        </link>
      </clipitem>""")

        audio_clips.append(f"""      <clipitem id="{aud_id}">
        <name>{escape_xml(name)}</name>
        <duration>{src_total_frames}</duration>
        <rate>
          <timebase>{timebase}</timebase>
          <ntsc>{ntsc_str}</ntsc>
        </rate>
        <start>{start_f}</start>
        <end>{end_f}</end>
        <in>{in_f}</in>
        <out>{out_f}</out>
        <file id="file-1"/>
        <sourcetrack>
          <mediatype>audio</mediatype>
          <trackindex>1</trackindex>
        </sourcetrack>
        <link>
          <linkclipref>{vid_id}</linkclipref>
          <mediatype>video</mediatype>
          <trackindex>1</trackindex>
          <clipindex>{i + 1}</clipindex>
        </link>
        <link>
          <linkclipref>{aud_id}</linkclipref>
          <mediatype>audio</mediatype>
          <trackindex>1</trackindex>
          <clipindex>{i + 1}</clipindex>
        </link>
      </clipitem>""")

    total_frames = timeline_cursor

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
  <sequence id="sequence-1">
    <name>{escape_xml(sequence_name)}</name>
    <duration>{total_frames}</duration>
    <rate>
      <timebase>{timebase}</timebase>
      <ntsc>{ntsc_str}</ntsc>
    </rate>
    <media>
      <video>
        <format>
          <samplecharacteristics>
            <width>{width}</width>
            <height>{height}</height>
            <rate>
              <timebase>{timebase}</timebase>
              <ntsc>{ntsc_str}</ntsc>
            </rate>
          </samplecharacteristics>
        </format>
        <track>
{os.linesep.join(video_clips)}
        </track>
      </video>
      <audio>
        <track>
{os.linesep.join(audio_clips)}
        </track>
      </audio>
    </media>
  </sequence>
</xmeml>
"""
    return xml


def escape_xml(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# الواجهة الرسومية
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("أداة قص السكتات التلقائي - CimaFast")
        self.geometry("560x520")
        self.resizable(False, False)

        self.video_path = tk.StringVar()
        self.noise_db = tk.StringVar(value="-35")
        self.min_silence = tk.StringVar(value="0.5")
        self.padding = tk.StringVar(value="0.15")
        self.min_keep = tk.StringVar(value="0.12")

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 16, "pady": 6}

        title = tk.Label(self, text="قص السكتات التلقائي", font=("Segoe UI", 16, "bold"))
        title.pack(pady=(16, 0))

        subtitle = tk.Label(
            self,
            text="اختار الفيديو، الأداة هتكتشف السكتات وتطلعلك XML تفتحه في Premiere",
            font=("Segoe UI", 10),
            fg="#555",
        )
        subtitle.pack(pady=(2, 12))

        file_frame = tk.Frame(self)
        file_frame.pack(fill="x", **pad)
        tk.Button(file_frame, text="اختار فيديو...", command=self.choose_file, width=16).pack(side="right")
        self.file_label = tk.Label(file_frame, text="(لسه محددتش فيديو)", anchor="e", fg="#333")
        self.file_label.pack(side="right", padx=10, fill="x", expand=True)

        settings_frame = tk.LabelFrame(self, text="الإعدادات (تقدر تسيبها زي ما هي)")
        settings_frame.pack(fill="x", **pad)

        self._add_setting(settings_frame, "حساسية اكتشاف الصمت (dB) - رقم أكبر (أقرب للصفر) = أحسس بالصوت الواطي", self.noise_db)
        self._add_setting(settings_frame, "أقل مدة صمت تتشال (بالثانية)", self.min_silence)
        self._add_setting(settings_frame, "هامش أمان حوالين الكلام (بالثانية) - يمنع قص أول/آخر حرف", self.padding)
        self._add_setting(settings_frame, "أقل مدة كلام تتحسب لقطة (بالثانية)", self.min_keep)

        self.start_btn = tk.Button(
            self, text="ابدأ التحليل واطلع XML", command=self.start, bg="#2e7d32", fg="white",
            font=("Segoe UI", 12, "bold"), height=2,
        )
        self.start_btn.pack(fill="x", **pad)

        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=16, pady=(0, 6))

        self.log = tk.Text(self, height=12, state="disabled", bg="#f5f5f5")
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _add_setting(self, parent, label, var):
        row = tk.Frame(parent)
        row.pack(fill="x", padx=8, pady=4)
        tk.Label(row, text=label, anchor="e", justify="right", wraplength=380).pack(side="right", fill="x", expand=True)
        tk.Entry(row, textvariable=var, width=8, justify="center").pack(side="left")

    def log_msg(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="اختار ملف الفيديو",
            filetypes=[("ملفات الفيديو", "*.mp4 *.mov *.mkv *.avi *.mxf *.m4v"), ("كل الملفات", "*.*")],
        )
        if path:
            self.video_path.set(path)
            self.file_label.config(text=os.path.basename(path))

    def start(self):
        path = self.video_path.get()
        if not path or not os.path.exists(path):
            messagebox.showerror("خطأ", "من فضلك اختار ملف فيديو موجود الأول.")
            return

        try:
            noise_db = float(self.noise_db.get())
            min_silence = float(self.min_silence.get())
            padding = float(self.padding.get())
            min_keep = float(self.min_keep.get())
        except ValueError:
            messagebox.showerror("خطأ", "من فضلك اكتب أرقام صح في الإعدادات.")
            return

        self.start_btn.config(state="disabled", text="جاري التحليل...")
        self.progress["value"] = 0
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.log_msg("بدأ التحليل... ده ممكن ياخد شوية دقايق على حسب طول الفيديو.")

        thread = threading.Thread(
            target=self._run, args=(path, noise_db, min_silence, padding, min_keep), daemon=True
        )
        thread.start()

    def _run(self, path, noise_db, min_silence, padding, min_keep):
        try:
            def on_progress(p):
                self.after(0, lambda: self.progress.config(value=p * 100))

            info = analyze_video(path, noise_db, min_silence, on_progress=on_progress)
            n_silences = len(info["silences"])
            self.after(0, lambda: self.log_msg(f"لقيت {n_silences} سكتة في الصوت."))

            keep = compute_keep_segments(info["duration"], info["silences"], padding, min_keep)
            if not keep:
                self.after(0, lambda: self._fail("مفيش أجزاء كلام واضحة اتلقت. جرب تقلل الحساسية أو تصغّر أقل مدة صمت."))
                return

            kept_duration = sum(e - s for s, e in keep)
            removed = info["duration"] - kept_duration
            self.after(0, lambda: self.log_msg(
                f"هيفضل {len(keep)} لقطة - مدتهم {kept_duration:.1f} ثانية "
                f"(هيتشال حوالي {removed:.1f} ثانية سكتات)."
            ))

            seq_name = os.path.splitext(os.path.basename(path))[0] + "_cut"
            xml = build_xmeml(path, keep, info, seq_name)

            out_path = os.path.splitext(path)[0] + "_قص_السكتات.xml"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(xml)

            self.after(0, lambda: self._done(out_path))
        except Exception as ex:
            msg = str(ex)
            self.after(0, lambda: self._fail(msg))

    def _done(self, out_path):
        self.start_btn.config(state="normal", text="ابدأ التحليل واطلع XML")
        self.progress["value"] = 100
        self.log_msg(f"تم! اتعمل الملف: {out_path}")
        self.log_msg("افتح Premiere > File > Import واختار الملف ده.")
        if messagebox.askyesno("تم بنجاح", "الملف اتعمل بنجاح.\nتحب تفتح الفولدر اللي فيه؟"):
            try:
                os.startfile(os.path.dirname(out_path))
            except Exception:
                pass

    def _fail(self, msg):
        self.start_btn.config(state="normal", text="ابدأ التحليل واطلع XML")
        self.log_msg("حصل خطأ: " + msg)
        messagebox.showerror("خطأ", msg)


if __name__ == "__main__":
    app = App()
    app.mainloop()
