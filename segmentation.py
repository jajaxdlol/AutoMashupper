from librosa import beat
from librosa import core
from librosa import feature
import matplotlib.pyplot as plt
from madmom.features.downbeats import DBNDownBeatTrackingProcessor as downbeattrack
from madmom.features.downbeats import RNNDownBeatProcessor as beatrnn
import numpy as np
from scipy.spatial.distance import cdist
import scipy.stats as st
import sys

eps = np.finfo(float).eps

def hz_to_pitch(hz_spectrums, sr):
    pitch_spectrums = []
    freq_scale = np.fft.fftfreq(hz_spectrums.shape[0])
    for hz_spectrum in hz_spectrums:
        pitch_spectrum = np.zeros(int(12*np.log2(int(sr/2)/440)) + 57)  # sr/2 is the maximum
        for freq in range(1, len(hz_spectrum)):
            pitch_spectrum[int(12*np.log2(freq_scale[freq]+eps/440)) + 57] += hz_spectrum[freq]
        pitch_spectrums.append(pitch_spectrum/max(pitch_spectrum))
    return np.array(pitch_spectrums).transpose()

def get_beat_sync_chroma(audio):
    y, sr = core.load(audio, sr=44100)
    tempo, _ = beat.beat_track(y, sr=sr, start_bpm=110, units='time', trim=False)
    act = beatrnn()(audio)
    beats = downbeattrack(beats_per_bar=[4, 4], fps=100)(act)
    downbeats = beats[beats[:, 1] == 1][:][:, 0]
    framed_dbn = np.concatenate([np.array([0]), downbeats ])

    # Calculate chroma semitone spectrum
    semitones = []
    chromas = []
    for i in range(1, len(framed_dbn)):
        stft = abs(core.stft(y[int(framed_dbn[i-1]*sr):int(framed_dbn[i]*sr)]))
        chroma = np.mean(feature.chroma_stft(y=None, S=stft**2), axis=1)
        semitone = np.mean(hz_to_pitch(stft, sr=sr), axis=1)
        chromas.append(chroma)
        semitones.append(semitone)
    chromas = np.array(chromas).transpose()
    semitones = np.array(semitones).transpose()

    # Plot the results and return the values
    time = np.arange(len(y)) / sr
    fig, ax = plt.subplots(3, 1)
    ax[0].plot(time, y)
    ax[0].vlines(framed_dbn, -1, 1, colors='r', linestyles='dashdot')
    ax[0].set_xlim(framed_dbn[0], framed_dbn[-1])
    plt.sca(ax[1])
    plt.pcolor(framed_dbn, np.arange(13), chromas)
    plt.yticks(np.arange(13)+0.5, ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])
    plt.ylim(0, 12)
    plt.sca(ax[2])
    plt.pcolor(semitones)
    print(tempo)

    return chromas, semitones, downbeats, tempo


def gkern(kernlen=21, nsig=3):
    """Returns a 2D Gaussian kernel."""
    x = np.linspace(-nsig, nsig, kernlen+1)
    kern1d = np.diff(st.norm.cdf(x))
    kern2d = np.outer(kern1d, kern1d)
    return kern2d/kern2d.sum()


def gcheckerboard(kernelen=64, nsig=32):
  """Return a 2D Gaussian checkerboard kernel."""
  c = np.array([[-1, 1], [1, -1]])
  intsize = int(np.ceil(kernelen/2))
  return np.kron(c, np.ones([intsize, intsize])) * gkern(kernelen, nsig)


def slidekernelthroughdiagonal(kernel, matrix):
  """Slide a kernel through a diagonal"""
  size_kernel = kernel.shape[0]
  size_matrix = matrix.shape[0]
  result = np.zeros([size_matrix])
  for i in range(size_matrix):
    # Calculate zero padding needed
    padding_b = -min(i - int(size_kernel/2), 0)
    padding_a = -min(size_matrix - int(i + size_kernel/2), 0)
    matrix_selection = matrix[max(0, i-int(size_kernel/2)):min(size_matrix, i+int(size_kernel/2)),max(0, i-int(size_kernel/2)):min(size_matrix, i+int(size_kernel/2))]
    matrix_padded = np.pad(matrix_selection, [(padding_b, padding_a), (padding_b, padding_a)])
    result[i] = np.sum(matrix_padded*kernel)
  return result


if __name__ == '__main__':
    if len(sys.argv) == 2:    
        chromas, semitones, downbeats, tempo = get_beat_sync_chroma(sys.argv[1])
        plt.figure()
        ss_semitones = cdist(semitones.transpose(), semitones.transpose(), metric='euclidean')
        plt.pcolor(ss_semitones)
        plt.show()