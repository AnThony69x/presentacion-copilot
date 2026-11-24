# Banda sonora sintetizada (sin derechos de autor) para intro.html: música + efectos sincronizados.
# Uso: python3 video/music.py  ->  video/music.wav (estéreo, 44.1 kHz)
# Los tiempos coinciden con las marcas data-in / PROMPTS / CAM de intro.html; si cambias la animación, ajústalos aquí.
import os, wave
import numpy as np

SR, DUR = 44100, 47.0
N = int(SR * DUR)
T = np.arange(N) / SR
rng = np.random.default_rng(7)
L = np.zeros(N); R = np.zeros(N)
BEAT = 0.5  # 120 bpm


def add(sig, t0, pan=0.0, gain=1.0, bus=None):
    """Suma una señal mono en t0 con paneo (-1 izq … 1 der)."""
    i = int(t0 * SR)
    if i >= N: return
    sig = sig[:N - i] * gain
    gl, gr = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    (bus or (L, R))[0][i:i + len(sig)] += sig * gl
    (bus or (L, R))[1][i:i + len(sig)] += sig * gr


def env(n, a=0.005, d=0.3):  # ataque lineal + caída exponencial
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def tone(f, dur, harm=(1,), detune=0.0):
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(t)
    for k, h in enumerate(harm, 1):
        for dt in ((0,) if not detune else (-detune, 0, detune)):
            out += h * np.sin(2 * np.pi * f * k * (1 + dt) * t + k)
    return out


def darken(x, w):  # filtro paso bajo simple (media móvil)
    return np.convolve(x, np.ones(w) / w, mode='same')


def noise(dur): return rng.standard_normal(int(dur * SR))


note = lambda m: 440 * 2 ** ((m - 69) / 12)
# progresión C – Am – F – G (un acorde cada 2 compases = 4 s)
PROG = [[48, 60, 64, 67], [45, 57, 60, 64], [41, 57, 60, 65], [43, 55, 59, 62]]
chord_at = lambda t: PROG[int(t // 4) % 4]

# ---------- bus musical (se atenúa con el bombo: sidechain) ----------
mL, mR = np.zeros(N), np.zeros(N)
M = (mL, mR)

# pad cálido: sierra suave desafinada, cambia cada 4 s, fundido entre acordes
for c in range(int(DUR // 4) + 1):
    t0 = c * 4.0
    for m in chord_at(t0)[1:]:
        s = tone(note(m), 4.6, harm=(1, .45, .22, .1, .05), detune=.004)
        s *= np.minimum(1, np.arange(len(s)) / (.6 * SR)) * np.minimum(1, (len(s) - np.arange(len(s))) / (.6 * SR))
        add(s, t0, pan=(m % 5 - 2) * .25, gain=.022, bus=M)

# bajo: corcheas sobre la raíz, desde la entrada del logo hasta el cierre
for k in range(int((43.2 - 6.0) / (BEAT / 2))):
    t0 = 6.0 + k * BEAT / 2
    f = note(chord_at(t0)[0] - 12 if k % 2 == 0 else chord_at(t0)[0])
    add(tone(f, .24, harm=(1, .5, .2)) * env(int(.24 * SR), .004, .12), t0, gain=.16, bus=M)

# arpegio pulsado en semicorcheas durante la demo, rebotando de lado a lado
pattern = [0, 1, 2, 3, 2, 1, 3, 2]
for k in range(int((38.6 - 10.2) / (BEAT / 4))):
    t0 = 10.2 + k * BEAT / 4
    ch = chord_at(t0)
    m = ch[1:][pattern[k % 8] % 3] + (12 if pattern[k % 8] == 3 else 0) + 12
    s = tone(note(m), .3, harm=(1, .3, .12)) * env(int(.3 * SR), .002, .09)
    add(s, t0, pan=.55 if k % 2 else -.55, gain=.035, bus=M)

# ---------- batería ----------
dL, dR = np.zeros(N), np.zeros(N)
D = (dL, dR)
duck = np.ones(N)
kick_n = int(.35 * SR)
kt = np.arange(kick_n) / SR
KICK = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt * 28)) / SR) * np.exp(-kt * 9)
CLAP = darken(noise(.25), 4) * env(int(.25 * SR), .002, .07) + .4 * tone(190, .25) * env(int(.25 * SR), .002, .05)
hat_raw = np.diff(noise(.06), prepend=0)
HAT = hat_raw * env(len(hat_raw), .001, .018)
beats = np.arange(6.0, 43.2, BEAT)
for b in beats:
    add(KICK, b, gain=.5, bus=D)
    i = int(b * SR); j = min(N, i + int(.28 * SR))
    duck[i:j] = np.minimum(duck[i:j], .45 + .55 * (np.arange(j - i) / (j - i)) ** .7)
    if 10.2 <= b < 38.6 and round((b - 6.0) / BEAT) % 2 == 1:
        add(CLAP, b, gain=.18, bus=D)
    if b >= 10.2:
        add(HAT, b + BEAT / 2, pan=.3, gain=.10, bus=D)
        if b < 38.6: add(HAT, b + BEAT / 4, pan=-.3, gain=.05, bus=D)

# ---------- efectos (sfx) ----------
sL, sR = np.zeros(N), np.zeros(N)
S = (sL, sR)


def whoosh(t0, dur=.55, pan_from=-.8, gain=.16):
    n = int(dur * SR); x = darken(noise(dur), 18) * 3
    shape = np.sin(np.pi * np.arange(n) / n) ** 2
    pan = np.linspace(pan_from, -pan_from, n)
    i = int((t0 - dur / 2) * SR)
    for ch, g in ((sL, np.sqrt((1 - pan) / 2)), (sR, np.sqrt((1 + pan) / 2))):
        ch[max(0, i):i + n] += (x * shape * g * gain)[max(0, -i):N - i]


def hit(t0, gain=.5, f=50):  # golpe grave para los "slams"
    n = int(.9 * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * np.cumsum(f + 140 * np.exp(-t * 25)) / SR) * np.exp(-t * 4.5)
    s += darken(noise(.9), 3) * np.exp(-t * 30) * .35
    add(s, t0, gain=gain, bus=S)


def pop(t0, f=900, gain=.10, pan=0.0):
    n = int(.12 * SR); t = np.arange(n) / SR
    add(np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * np.exp(-t * 60))) / SR) * np.exp(-t * 40), t0, pan, gain, S)


def bell(t0, freqs, gain=.08, dec=1.2):
    for f in freqs:
        s = tone(f, dec * 3, harm=(1, .0, .35, .0, .15)) * env(int(dec * 3 * SR), .002, dec)
        add(s, t0, pan=rng.uniform(-.4, .4), gain=gain, bus=S)


# gancho: tics del contador (más rápidos al inicio, como la curva ease-out)
for k in range(1, 40):
    p = k / 40; u = 1 - (1 - p) ** (1 / 3)  # inversa de ease-out cúbico
    pop(.2 + 1.4 * u, f=1800 + 20 * k, gain=.09, pan=rng.uniform(-.3, .3))
hit(1.62, .35, 70)
# subida antes del logo
n = int(1.5 * SR); rt = np.arange(n) / SR
riser = darken(noise(1.5), 6) * (rt / 1.5) ** 2 * 1.4 + .3 * np.sin(2 * np.pi * np.cumsum(200 + 600 * (rt / 1.5) ** 2) / SR) * (rt / 1.5) ** 2
add(riser, 4.6, gain=.18, bus=S)
for t0 in (3.6, 3.8, 4.0, 4.2, 4.5): hit(t0, .32, 80)
hit(4.8, .3, 60)
hit(6.1, .6, 42); bell(6.1, [note(72), note(76), note(79)], .05, 1.6)
pop(7.1, 1200, .07)
for t0 in (8.4, 8.9, 9.4): hit(t0, .45, 55)
for t0 in (3.4, 8.2, 10.2, 21.4, 30.4, 38.6, 43.1): whoosh(t0, pan_from=-.8 if int(t0) % 2 else .8)

# tecleo durante los prompts (mismos tiempos que PROMPTS en intro.html)
for a, b in ((11.0, 12.6), (18.3, 18.8), (22.8, 23.5), (31.0, 32.4)):
    t0 = a
    while t0 < b:
        k = darken(noise(.03), 2) * env(int(.03 * SR), .0005, .006)
        add(k, t0, pan=rng.uniform(-.25, .25), gain=rng.uniform(.05, .09), bus=S)
        t0 += rng.uniform(.035, .075)
# enviar prompt: blip ascendente
for t0 in (12.85, 18.95, 23.65, 32.55):
    n = int(.18 * SR); t = np.arange(n) / SR
    add(np.sin(2 * np.pi * np.cumsum(500 + 1400 * t / .18) / SR) * np.sin(np.pi * t / .18), t0, .2, .07, S)
# respuestas y tarjetas que aparecen
for t0 in (13.6, 17.3, 24.3, 33.2): pop(t0, 700, .08)
for k, t0 in enumerate((24.6, 25.4, 26.2, 33.6, 34.0, 34.4)): pop(t0, 900 + 120 * (k % 3), .08, (k % 3 - 1) * .4)
for k, t0 in enumerate((39.2, 39.5, 39.8, 40.1, 40.4, 40.7)): pop(t0, 800 + 90 * k, .08, (-1) ** k * .5)
# clic en «Más breve», guardado en Borradores y llegada del borrador
pop(16.9, 2400, .09)
bell(19.4, [note(84), note(88)], .05, .5)
whoosh(20.15, .9, -.6, .10)
bell(20.65, [note(91)], .06, .6)
hit(38.8, .4, 55)
# cierre: acorde de campana con el logo y la marca
hit(43.8, .45, 45); bell(43.8, [note(m) for m in (60, 64, 67, 72, 76)], .045, 2.2)
pop(44.5, 1100, .06)

# ---------- mezcla ----------
mL *= duck; mR *= duck
L += mL + dL + sL; R += mR + dR + sR
# reverb: convolución con ruido de caída exponencial (distinto por canal para dar amplitud)
ir_n = int(1.6 * SR); it = np.arange(ir_n) / SR
for ch, seed in ((L, 1), (R, 2)):
    ir = np.random.default_rng(seed).standard_normal(ir_n) * np.exp(-it * 3.2)
    ir = darken(ir, 5); ir /= np.sqrt((ir ** 2).sum())
    size = 1 << int(np.ceil(np.log2(N + ir_n)))
    wet = np.fft.irfft(np.fft.rfft(ch, size) * np.fft.rfft(ir, size), size)[:N]
    ch += wet * .28
fade = np.minimum(1, np.minimum(T / .05, (DUR - T) / 2.0))
L *= fade; R *= fade
mix = np.stack([L, R], axis=1)
mix = np.tanh(mix / np.abs(mix).max() * 1.6) / np.tanh(1.6) * .89  # saturación suave y pico a −1 dBFS
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'music.wav')
with wave.open(path, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok', path)
