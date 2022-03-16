#!/usr/bin/env python3
import argparse
import pathlib
import random
from string import Template
import subprocess
import tempfile
import time

lilypond_midi_score = Template(r'''
\version "2.22.2"

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
}
''')

lilypond_layout_score = Template(r'''
\version "2.22.2"

\paper {
  #(set-paper-size "a6landscape")
}

\score {
  \new Staff {
    \relative c' {
      \tempo 4 = $tempo
      \numericTimeSignature
      \time $timeSignature
      \set Staff.midiInstrument = "acoustic grand"
      \voiceOne
      $notes
    }
  }
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
    arg_parser.add_argument(
        '-t', '--tempo', type=int, default=80,
        help='tempo (bpm) used to play the rhythm (default: 80)'
    )
    arg_parser.add_argument(
        '-m', '--measures', type=int, default=4,
        help='number of measures in the rhythm (default: 4)'
    )
    args = arg_parser.parse_args()

    with tempfile.TemporaryDirectory(prefix='rhythmic_dictation') as temp_dir:
        print(f'Created temporary directory {temp_dir}')

        layout_score_fn = 'layout_score.ly'
        layout_score_file = open(
            pathlib.Path(temp_dir) / layout_score_fn, 'w', encoding='utf-8'
        )
        midi_score_fn = 'midi_score.ly'
        midi_score_file = open(
            pathlib.Path(temp_dir) / midi_score_fn, 'w', encoding='utf-8'
        )

        bpmeasure = random.choice((2, 3, 4))
        measures = args.measures

        notes = []
        for _ in range(measures):
            notes.extend(gen_beats(beats=bpmeasure))

        notes_lilypond = ' '.join(
            map(lambda n: 'c' + eighths_to_lilypond(n), notes)
        )

        layout_score_string = lilypond_layout_score.substitute(
            tempo=args.tempo, timeSignature=f'{bpmeasure}/4',
            notes=notes_lilypond
        )
        midi_score_string = lilypond_midi_score.substitute(
            tempo=args.tempo, timeSignature=f'{bpmeasure}/4',
            notes=notes_lilypond
        )
        layout_score_file.write(layout_score_string)
        layout_score_file.flush()
        midi_score_file.write(midi_score_string)
        midi_score_file.flush()
        input()

        subprocess.run(('lilypond', '--png', layout_score_fn), check=True,
                       cwd=temp_dir)
        subprocess.run(('lilypond', midi_score_fn), check=True, cwd=temp_dir)

        for _ in range(3):
            subprocess.run(('timidity', 'midi_score.midi'), check=True,
                           cwd=temp_dir)
            time.sleep(5)

        subprocess.run(('feh', 'layout_score.png'), check=True, cwd=temp_dir)

        layout_score_file.close()
        midi_score_file.close()


if __name__ == '__main__':
    main()
