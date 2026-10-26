#!/usr/bin/env python3
"""ESP32 CAN logger .jsonl dosyalarindan ID basina ozet cikarir.

Kullanim: python3 analyze_captures.py <jsonl_klasoru> [min_kare=200]

- Extended kareleri ve az gorulen (gurultu) ID'leri atar.
- Her bayt icin: sabit / enum / sayac / analog / crc-benzeri siniflandirmasi.
- VIN parcalari tasiyan 0x710-0x712 kareleri ciktida maskelenir.
"""
import glob, json, math, sys, collections

VIN_IDS = {"0x710", "0x711", "0x712"}

def load(folder):
    per = collections.defaultdict(list)
    for f in sorted(glob.glob(f"{folder}/**/*.jsonl", recursive=True)):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    if r.get("extended"):
                        continue
                    data = bytes.fromhex(r["data_hex"].replace(" ", ""))
                except (ValueError, KeyError):
                    continue
                per[r["can_id"]].append(data)
    return per

def classify(vals):
    c = collections.Counter(vals)
    if len(c) == 1:
        return "sabit"
    if len(c) <= 6:
        return "enum"
    d = [abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
    small = sum(x <= 2 for x in d) / max(1, len(d))
    inc = sum((vals[i + 1] - vals[i]) % 256 == 1 for i in range(len(vals) - 1)) / max(1, len(d))
    if inc > 0.3:
        return "sayac?"
    return "analog" if small > 0.5 else "crc/gurultu"

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    min_n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    per = load(sys.argv[1])
    for cid, frames in sorted(per.items(), key=lambda kv: -len(kv[1])):
        if len(frames) < min_n and cid not in VIN_IDS:
            continue
        if cid in VIN_IDS:
            print(f"{cid}: {len(frames)} kare (VIN parcasi, maskelendi)")
            continue
        n = collections.Counter(len(f) for f in frames).most_common(1)[0][0]
        fr = [f for f in frames if len(f) == n]
        print(f"{cid}: {len(fr)} kare, DLC {n}")
        for k in range(n):
            vals = [f[k] for f in fr]
            top = collections.Counter(vals).most_common(3)
            print(f"  B{k}: {classify(vals):12s} uniq={len(set(vals)):3d} "
                  f"top={' '.join('%02X:%d' % t for t in top)}")

if __name__ == "__main__":
    main()
