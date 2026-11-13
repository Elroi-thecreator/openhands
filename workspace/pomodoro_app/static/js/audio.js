

// Web Audio API Audio Synthesizer for Alerts and Ambient Noise
class SoundEngine {
    constructor() {
        this.audioCtx = null;
        this.ambientGainNode = null;
        this.activeAmbientNodes = [];
        this.ambientType = null;
    }

    initCtx() {
        if (!this.audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioCtx = new AudioContext();
        }
        if (this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
    }

    playAlert(soundType, volumePercent = 80) {
        this.initCtx();
        if (soundType === 'none') return;

        const volume = (volumePercent / 100) * 0.5; // normalize volume max

        switch (soundType) {
            case 'bell':
                this.playBellSound(volume);
                break;
            case 'beep':
                this.playBeepSound(volume);
                break;
            case 'marimba':
                this.playMarimbaChime(volume);
                break;
            case 'fanfare':
                this.playFanfare(volume);
                break;
            default:
                this.playBellSound(volume);
                break;
        }
    }

    playBellSound(vol) {
        const now = this.audioCtx.currentTime;
        
        // Two harmonics for a warm digital bell
        const freqs = [523.25, 1046.50]; // C5, C6
        freqs.forEach((freq, idx) => {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, now);

            gain.gain.setValueAtTime(vol / (idx + 1), now);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.8);

            osc.connect(gain);
            gain.connect(this.audioCtx.destination);

            osc.start(now);
            osc.stop(now + 1.8);
        });
    }

    playBeepSound(vol) {
        const now = this.audioCtx.currentTime;
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();

        osc.type = 'square';
        osc.frequency.setValueAtTime(880, now); // A5

        gain.gain.setValueAtTime(vol * 0.4, now);
        gain.gain.setValueAtTime(0.0001, now + 0.15);

        osc.connect(gain);
        gain.connect(this.audioCtx.destination);

        osc.start(now);
        osc.stop(now + 0.15);

        // Second beep
        const osc2 = this.audioCtx.createOscillator();
        const gain2 = this.audioCtx.createGain();
        osc2.type = 'square';
        osc2.frequency.setValueAtTime(880, now + 0.2);

        gain2.gain.setValueAtTime(vol * 0.4, now + 0.2);
        gain2.gain.setValueAtTime(0.0001, now + 0.35);

        osc2.connect(gain2);
        gain2.connect(this.audioCtx.destination);

        osc2.start(now + 0.2);
        osc2.stop(now + 0.35);
    }

    playMarimbaChime(vol) {
        const now = this.audioCtx.currentTime;
        const notes = [523.25, 659.25, 783.99, 1046.50]; // C, E, G, C arpeggio

        notes.forEach((freq, i) => {
            const startTime = now + i * 0.12;
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, startTime);

            gain.gain.setValueAtTime(vol * 0.8, startTime);
            gain.gain.exponentialRampToValueAtTime(0.0001, startTime + 0.8);

            osc.connect(gain);
            gain.connect(this.audioCtx.destination);

            osc.start(startTime);
            osc.stop(startTime + 0.8);
        });
    }

    playFanfare(vol) {
        const now = this.audioCtx.currentTime;
        const melody = [
            { freq: 523.25, time: 0, dur: 0.15 },
            { freq: 659.25, time: 0.15, dur: 0.15 },
            { freq: 783.99, time: 0.30, dur: 0.15 },
            { freq: 1046.50, time: 0.45, dur: 0.5 }
        ];

        melody.forEach(note => {
            const startTime = now + note.time;
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();

            osc.type = 'triangle';
            osc.frequency.setValueAtTime(note.freq, startTime);

            gain.gain.setValueAtTime(vol * 0.7, startTime);
            gain.gain.exponentialRampToValueAtTime(0.0001, startTime + note.dur);

            osc.connect(gain);
            gain.connect(this.audioCtx.destination);

            osc.start(startTime);
            osc.stop(startTime + note.dur);
        });
    }

    // --- AMBIENT SOUND SYNTHESIS ---

    setAmbientVolume(volPercent) {
        if (this.ambientGainNode) {
            const targetVol = (volPercent / 100) * 0.3;
            this.ambientGainNode.gain.setTargetAtTime(targetVol, this.audioCtx.currentTime, 0.1);
        }
    }

    stopAmbient() {
        this.activeAmbientNodes.forEach(node => {
            try { node.stop(); } catch(e){}
            try { node.disconnect(); } catch(e){}
        });
        this.activeAmbientNodes = [];
        this.ambientType = null;
    }

    toggleAmbient(type, volumePercent = 40) {
        this.initCtx();

        if (this.ambientType === type) {
            this.stopAmbient();
            return false;
        }

        this.stopAmbient();
        this.ambientType = type;

        const bufferSize = 2 * this.audioCtx.sampleRate;
        const noiseBuffer = this.audioCtx.createBuffer(1, bufferSize, this.audioCtx.sampleRate);
        const output = noiseBuffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            output[i] = Math.random() * 2 - 1;
        }

        const whiteNoise = this.audioCtx.createBufferSource();
        whiteNoise.buffer = noiseBuffer;
        whiteNoise.loop = true;

        this.ambientGainNode = this.audioCtx.createGain();
        this.setAmbientVolume(volumePercent);

        if (type === 'rain') {
            // Low-pass filter for rain effect
            const filter = this.audioCtx.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.value = 1000;

            whiteNoise.connect(filter);
            filter.connect(this.ambientGainNode);
        } else if (type === 'ocean') {
            // Low-pass filter with LFO for wave modulation
            const filter = this.audioCtx.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.value = 400;

            const lfo = this.audioCtx.createOscillator();
            lfo.frequency.value = 0.12; // Slow swell
            const lfoGain = this.audioCtx.createGain();
            lfoGain.gain.value = 300;

            lfo.connect(lfoGain);
            lfoGain.connect(filter.frequency);
            lfo.start();

            whiteNoise.connect(filter);
            filter.connect(this.ambientGainNode);
            this.activeAmbientNodes.push(lfo);
        } else {
            // White / Pink Noise
            const filter = this.audioCtx.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.value = 3000;

            whiteNoise.connect(filter);
            filter.connect(this.ambientGainNode);
        }

        this.ambientGainNode.connect(this.audioCtx.destination);
        whiteNoise.start();
        this.activeAmbientNodes.push(whiteNoise);
        return true;
    }
}

const soundEngine = new SoundEngine();

