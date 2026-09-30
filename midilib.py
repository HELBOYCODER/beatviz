"""Minimal pure-Python MIDI parser (no dependencies).

Parses format 0/1 MIDI files into tracks of note events.
"""

import struct


def _read_varlen(data, pos):
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos


class Note:
    __slots__ = ("start", "end", "pitch", "velocity", "track", "channel")

    def __init__(self, start, end, pitch, velocity, track, channel):
        self.start = start      # seconds
        self.end = end          # seconds
        self.pitch = pitch      # 0-127
        self.velocity = velocity
        self.track = track
        self.channel = channel

    @property
    def duration(self):
        return max(0.01, self.end - self.start)

    def __repr__(self):
        return f"Note({self.pitch}, {self.start:.2f}-{self.end:.2f})"


class MidiFile:
    def __init__(self, path, tempo_override=None):
        raw = open(path, "rb").read()
        if raw[:4] != b"MThd":
            raise ValueError("not a MIDI file (missing MThd)")
        header_len = struct.unpack(">I", raw[4:8])[0]
        fmt, ntrks, division = struct.unpack(">HHH", raw[8:14])
        self.format = fmt
        self.division = division
        pos = 8 + header_len

        # ticks -> seconds needs tempo map; collect all tempo changes first
        self.tempos = [(0.0, 500000, 0.0)]  # (abs_tick, us_per_quarter, abs_seconds)
        raw_tracks = []
        for _ in range(ntrks):
            if raw[pos:pos + 4] != b"MTrk":
                break
            tlen = struct.unpack(">I", raw[pos + 4:pos + 8])[0]
            raw_tracks.append(raw[pos + 8:pos + 8 + tlen])
            pos += 8 + tlen

        self.tempo_changes = []
        for tdata in raw_tracks:
            self.tempo_changes.extend(self._scan_tempos(tdata))
        if tempo_override:
            self.tempo_changes = [(0, int(60_000_000 / float(tempo_override)))]
        self.tempo_changes.sort(key=lambda t: t[0])

        if division & 0x8000:
            # SMPTE: frames/second in high byte, ticks per frame in low byte
            fps = 256 - (division >> 8)
            self.tps = fps * (division & 0xFF)
        else:
            self.tps = division  # ticks per quarter note

        self.tempo_override = tempo_override

        self.notes = []
        for idx, tdata in enumerate(raw_tracks):
            self.notes.extend(self._parse_track(tdata, idx))
        self.notes.sort(key=lambda n: n.start)

    # ---- tempo ----
    @staticmethod
    def _scan_tempos(tdata):
        changes = []
        pos = 0
        running = 0
        while pos < len(tdata):
            delta, pos = _read_varlen(tdata, pos)
            if pos >= len(tdata):
                break
            status = tdata[pos]
            if status & 0x80:
                pos += 1
                running = status
            else:
                status = running
            if status == 0xFF:
                mtype = tdata[pos]
                pos += 1
                ln, pos = _read_varlen(tdata, pos)
                if mtype == 0x51 and ln >= 3:
                    changes.append((pos - delta, int.from_bytes(tdata[pos:pos + 3], "big")))
                pos += ln
            elif status in (0xF0, 0xF7):
                ln, pos = _read_varlen(tdata, pos)
                pos += ln
            else:
                hi = status & 0xF0
                if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                    pos += 2
                elif hi in (0xC0, 0xD0):
                    pos += 1
        return changes

    def _tick_to_sec(self, tick):
        if self.tempo_override:
            us = int(60_000_000 / float(self.tempo_override))
            return tick / self.tps * (us / 1_000_000.0)
        sec = 0.0
        last_tick = 0
        us = 500000
        for t, new_us in self.tempo_changes:
            if t > tick:
                break
            sec += (t - last_tick) / self.tps * (us / 1_000_000.0)
            last_tick = t
            us = new_us
        sec += (tick - last_tick) / self.tps * (us / 1_000_000.0)
        return sec

    # ---- notes ----
    def _parse_track(self, tdata, track_idx):
        notes = []
        pos = 0
        tick = 0
        running = 0
        active = {}
        while pos < len(tdata):
            delta, pos = _read_varlen(tdata, pos)
            tick += delta
            if pos >= len(tdata):
                break
            status = tdata[pos]
            if status & 0x80:
                pos += 1
                running = status
            else:
                status = running
            if status == 0xFF:
                mtype = tdata[pos]
                pos += 1
                ln, pos = _read_varlen(tdata, pos)
                pos += ln
                continue
            if status in (0xF0, 0xF7):
                ln, pos = _read_varlen(tdata, pos)
                pos += ln
                continue
            hi = status & 0xF0
            ch = status & 0x0F
            if hi == 0x90:
                pitch, vel = tdata[pos], tdata[pos + 1]
                pos += 2
                if vel == 0:
                    key = (ch, pitch)
                    if key in active:
                        st = active.pop(key)
                        notes.append(Note(self._tick_to_sec(st), self._tick_to_sec(tick),
                                          pitch, vel, track_idx, ch))
                else:
                    active[(ch, pitch)] = tick
            elif hi == 0x80:
                pitch, vel = tdata[pos], tdata[pos + 1]
                pos += 2
                key = (ch, pitch)
                if key in active:
                    st = active.pop(key)
                    notes.append(Note(self._tick_to_sec(st), self._tick_to_sec(tick),
                                      pitch, vel, track_idx, ch))
            elif hi in (0xA0, 0xB0, 0xE0):
                pos += 2
            elif hi in (0xC0, 0xD0):
                pos += 1
        for (ch, pitch), st in active.items():
            notes.append(Note(self._tick_to_sec(st), self._tick_to_sec(tick),
                              pitch, 64, track_idx, ch))
        return notes

    def pitch_range(self):
        if not self.notes:
            return (60, 72)
        return (min(n.pitch for n in self.notes), max(n.pitch for n in self.notes))

    def parts(self):
        """Group notes into parts by (track, channel) for per-part drawing."""
        groups = {}
        for n in self.notes:
            groups.setdefault((n.track, n.channel), []).append(n)
        return groups
