#!/usr/bin/env python3
import argparse
import logging
import pathlib
import random
import shutil
from string import Template
import subprocess
import sys
import tempfile

lilypond_midi_score = Template(r'''\version "2.22.2"

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
}''')

lilypond_layout_score = Template(r'''\version "2.22.2"

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
}''')


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


def parse_args():
    arg_parser = argparse.ArgumentParser(
        description='Practice rhythmic dictation',
        usage='%(prog)s [options]'
    )

    def tempo(arg):
        iarg = int(arg)
        if iarg < 1:
            raise ValueError('Tempo must be greater than 0')
        return iarg
    arg_parser.add_argument(
        '-t', dest='tempo', type=tempo, default=80,
        help='tempo (bpm) used to play the rhythm (default: 80)'
    )

    def measures(arg):
        iarg = int(arg)
        if iarg < 1:
            raise ValueError('Number of measures must be greater than 0')
        return iarg
    arg_parser.add_argument(
        '-m', dest='measures', type=measures, default=4,
        help='number of measures in the rhythm (default: 4)'
    )

    def note_values(arg):
        valid_values = (8, 6, 4, 3, 2, 1)
        try:
            parsed = tuple(map(int, arg.split(',')))
            if not all(map(lambda n: n in valid_values, parsed)):
                raise ValueError(f'Note values must be one of {valid_values}')
            return parsed
        except ValueError as e:
            raise ValueError(f'Invalid list of notes: {e.args}') from e
    arg_parser.add_argument(
        '-n', dest='note_values', default='8,6,4,3,2,1', type=note_values,
        help='note values to use in number of 8ths per note, comma separated'
    )

    def external_program(arg):
        if shutil.which(arg) is None:
            raise FileNotFoundError(f'external program {arg} not found')
        return arg

    arg_parser.add_argument(
        '--image-viewer', type=external_program, default='feh',
        help='program used to view correct answer (default: feh)'
    )

    arg_parser.add_argument(
        '--midi-player', type=external_program, default='timidity',
        help='program used to play MIDI file of the rhythm (default: timidity)'
    )

    arg_parser.add_argument(
        '--lilypond-path', type=external_program, default='lilypond',
        help='location of lilypond executable (can be in PATH, default: lilypond)'
    )

    arg_parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='display debug messages and output of subprocesses'
    )

    args = arg_parser.parse_args()

    return args


def configure_logging():
    logging.basicConfig(format='%(levelname)s:%(message)s',
                        level=logging.DEBUG)


def main():
    configure_logging()
    args = parse_args()

    level = logging.WARNING
    if args.verbose:
        level = logging.DEBUG
    logging.getLogger().setLevel(level)

    out = None
    err = None
    if not args.verbose:
        out = subprocess.DEVNULL
        err = subprocess.DEVNULL

    with tempfile.TemporaryDirectory(prefix='rhythmic_dictation') as temp_dir:
        logging.info('Created temporary directory %s', temp_dir)

        layout_score_fn = pathlib.Path(temp_dir) / 'layout_score.ly'
        layout_score_file = open(layout_score_fn, 'w', encoding='utf-8')
        logging.info('Created layout lilypond score file %s',
                     layout_score_fn)
        midi_score_fn = pathlib.Path(temp_dir) / 'midi_score.ly'
        midi_score_file = open(midi_score_fn, 'w', encoding='utf-8')
        logging.info('Created lilypond score file for MIDI output %s',
                     midi_score_fn)

        bpmeasure = random.choice((2, 3, 4))
        measures = args.measures

        logging.info('Generating notes ...')
        notes = []
        for _ in range(measures):
            notes.extend(gen_beats(beats=bpmeasure,
                                   note_values=args.note_values))

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

        logging.info('Converting %s to image ...', layout_score_fn)
        subprocess.run(
            (args.lilypond_path, '--png', layout_score_fn),
            check=True,
            cwd=temp_dir,
            stdout=out,
            stderr=err,
            text=True
        )
        logging.info('Converting %s to midi ...', midi_score_fn)
        subprocess.run(
            (args.lilypond_path, midi_score_fn),
            check=True,
            cwd=temp_dir,
            stdout=out,
            stderr=err,
            text=True
        )

        again = True
        while again:
            logging.info('Playing midi ...')
            subprocess.run(
                (args.midi_player, 'midi_score.midi'),
                check=True,
                cwd=temp_dir,
                stdout=out,
                stderr=err,
                text=True
            )
            again = input('Listen again (y/n)? ')
            if again.lower() == 'n':
                break

        logging.info('Showing correct answer')
        subprocess.run((args.image_viewer, 'layout_score.png'), check=True,
                       cwd=temp_dir, stdout=out, stderr=err, text=True)

        layout_score_file.close()
        midi_score_file.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
