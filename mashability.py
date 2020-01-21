import numpy as np
from scipy import signal
from segmentation import get_beat_sync_chroma, get_beat_sync_spectrums
from librosa.output import write_wav
import glob
from utilities import mix_songs
import sys, csv, shutil

def mashability(base_beat_sync_chroma, base_beat_sync_spec, audio_file_candidate):
    """
    Calculate mashability for a beat_sync_chroma and a audio_file_candidate
    returns the 2dconv_matrix normalised of the two_chromas, the max mashability achieved,
    the
    """
    # 1st step: Calculate harmonic compatibility
    c_bsc = np.flip(get_beat_sync_chroma(audio_file_candidate), )  # Flip to ensure max mashability with
    stacked_beat_sync_chroma = np.vstack([c_bsc, c_bsc])
    conv = signal.convolve2d(stacked_beat_sync_chroma, base_beat_sync_chroma, )
    base_n = np.linalg.norm(base_beat_sync_chroma)
    cand_n = np.linalg.norm(c_bsc)
    h_mas = conv / (base_n * cand_n)
    offset = base_beat_sync_chroma.shape[1]
    offset -= 1 if offset % 2 == 0 else 2
    h_mas_k = np.max(h_mas[:, offset:-offset], axis=0)  # Get only valid values on beat axis

    # 3rd step: Calculate Spectral balance compatibility
    c_bss = get_beat_sync_spectrums(audio_file_candidate)

    if c_bss.shape[1] >= base_beat_sync_spec.shape[1]:
        beat_length = base_beat_sync_spec.shape[1]
        n_max_b_shifts = c_bss.shape[1] - base_beat_sync_spec.shape[1]
        r_mas_k = np.zeros(n_max_b_shifts+1)
        for i in range(n_max_b_shifts+1):
            beta = np.sum(base_beat_sync_spec + c_bss[:, i:i + beat_length], axis=0)
            beta_norm = beta/np.sum(beta)
            r_mas_k[i] = 1 - np.std(beta_norm)
    else:
        raise ValueError("Candidate song has lesser beats than base song")


    res_mash = h_mas_k + 0.2 * r_mas_k

    b_offset = np.argmax(res_mash)
    p_shift =  6 - np.argmax(h_mas[5:18, offset + b_offset])
    return conv, np.max(res_mash), p_shift, b_offset


def main():
    if len(sys.argv) < 2:
        print("Usage: python mashability.py <base_song>")
        return
    elif '-p' not in sys.argv:
        base_song = sys.argv[1]
        base_schroma = get_beat_sync_chroma(base_song)
        base_spec = get_beat_sync_spectrums(base_song)
        songs = glob.glob("audio_files/*.mp3")
        mashabilities = {}
        valid_songs = []
        mashability(base_schroma,
                    base_spec,
                    base_song)
        for cand_song in songs:
            try:
                mashabilities[cand_song] = mashability(base_schroma,
                                                       base_spec,
                                                       cand_song)[1:]
                valid_songs.append(cand_song)
            except ValueError as e:
                print("Skipping song %s, because %s" % (cand_song, str(e)))

        valid_songs.sort(key=lambda x: mashabilities[x][0], reverse=True)
        top_10 = valid_songs[:10]

        with open(base_song.split('/')[-1].replace('.mp3', '.csv'), 'w') as csvfile:
            csvfile.write("file,mashability,pitch_shift,beat_offset\n")
            for cand_song in top_10:
                out_file = "audio_files/%s" % (cand_song.split('/')[-1])
                csvfile.write("%s,%s,%s,%s\n" % (out_file, mashabilities[cand_song][0], mashabilities[cand_song][1],
                                                 mashabilities[cand_song][2]))
    base_song = sys.argv[1]
    with open(base_song.split('/')[-1].replace('.mp3', '.csv'), 'r') as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            cand_song = row['file']
            pitch_shift = int(row['pitch_shift'])
            beat_offset = int(row['beat_offset'])
            mix = mix_songs(base_song, cand_song, beat_offset, pitch_shift)
            out_file = "results/%s_MIXED_%s" % (row['mashability'], cand_song.split('/')[-1].replace('.mp3', '.wav'))
            # Copy the original candidate to the results folder
            original_cand_copy = "results/ORIGINAL_%s" % (cand_song.split('/')[-1])
            shutil.copyfile(cand_song, original_cand_copy)
            write_wav(out_file, mix, 44100)

if __name__ == '__main__':
    main()
