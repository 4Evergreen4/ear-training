#!/usr/bin/env python3
import argparse
import pathlib
import random
from string import Template
import subprocess
import tempfile
import time


lilypond_score = Template(r'''
\version "2.22.2"

\paper {
  #(set-paper-size "a5landscape")
}

\score {
  \new Staff {
    \relative {
      \tempo 4 = $tempo
      \numericTimeSignature
      \time 4/4

      \set Staff.midiInstrument = "timpani"
      \voiceOne
      c' c c c

      \time $timeSignature
      \set Staff.midiInstrument = "acoustic grand"
      \voiceOne
      $notes
    }
  }
  \midi { }
  \layout { }

}
''')


def gen_beats(beats=4, note_values=(8, 6, 4, 3, 2, 1)):
    # note that a quarter note always gets a beat here
    notes = [0]
    eighths = beats * 2
    current_eighths = 0
    while current_eighths != eighths:
        current_eighths -= notes.pop()

        while current_eighths < eighths:
            note_val = random.choice(note_values)
            notes.append(note_val)
            current_eighths += note_val

    return notes


def eighths_to_lilypond(eighths):
    eighths_to_vals = {
        8: '1',
        6: '2.',
        4: '2',
        3: '4.',
        2: '4',
        1: '8',
    }
    return eighths_to_vals[eighths]


def main():
    arg_parser = argparse.ArgumentParser(
        description='Practice rhythmic dictation'
    )

    with tempfile.TemporaryDirectory(prefix='rhythmic_dictation') as temp_dir:
        print(f'Created temporary directory {temp_dir}')

        score_fn = 'score.ly'
        score_file = open(pathlib.Path(temp_dir) / score_fn, 'w',
                          encoding='utf-8')

        bpmeasure = random.choice((2, 3, 4))
        measures = 4
        beats = bpmeasure * measures

        notes = gen_beats(beats=beats)
        notes = []
        for _ in range(measures):
            notes.extend(gen_beats(beats=bpmeasure))

        notes_lilypond = map(lambda n: 'c' + eighths_to_lilypond(n), notes)

        score_string = lilypond_score.substitute(
            tempo=60, timeSignature=f'{bpmeasure}/4',
            notes=' '.join(notes_lilypond)
        )
        score_file.write(score_string)
        score_file.flush()

        subprocess.run(('lilypond', '--png', score_fn), check=True,
                       cwd=temp_dir)

        # for _ in range(3):
        #     subprocess.run(('timidity', 'score.midi'), check=True,
        #                    cwd=temp_dir)
        #     time.sleep(5)

        subprocess.run(('feh', 'score.png'), check=True, cwd=temp_dir)

        score_file.close()


if __name__ == '__main__':
    main()
