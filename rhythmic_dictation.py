#!/usr/bin/env python3
'''Simple application for practicing rhythmic dictation.'''

import argparse
import logging
import pathlib
import random
import shutil
from string import Template
import subprocess
import sys
import tempfile
from typing import List, Sequence
from typed_argparse import TypedArgs  # type: ignore

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


def gen_rhythm(beats: int = 4,
               note_values: Sequence[int] = (8, 6, 4, 3, 2, 1)) -> Sequence[int]:
    '''Generates a rhythm of the given length with the given note values.

    Args:
      beats: Length of the rhythm to generate in quarter notes (default 4)
      note_values: The note values in 8th notes to use when generating the
        rhythm. For instance, a quarter note's note value would be 2 (two
        8th notes). (default (8, 6, 4, 3, 2, 1))

    Returns:
      A sequence of notes by their values in 8ths. For example, [1, 3] would
      be an 8th note followed by a dotted quarter note.

    Raises:
      ValueError: It may not be possible to generate a rhythm of a given
        length given specific note values. If that happens, this error
        is raised.
    '''

    iter_max = 500

    notes = [0]
    eighths = beats * 2
    current_eighths = 0
    iter_counter = 0
    while current_eighths != eighths:
        iter_counter += 1
        if iter_counter > iter_max:
            raise ValueError(
                'Given note values cannot create rhythm of the given length'
            )

        current_eighths -= notes.pop()

        while current_eighths < eighths:
            note_val = random.choice(note_values)
            notes.append(note_val)
            current_eighths += note_val

    return notes


def eighths_to_lilypond(eighths: int) -> str:
    '''Converts from note value in 8ths to lilypond note length.

    Args:
      note_values: The note valuein 8ths to convert. For example, a quarter
        note's value would be 2.

    Returns:
      A sequence of notes by their values in 8ths. For example, [1, 3] would
      be an 8th note followed by a dotted quarter note.

    Raises:
      KeyError: The given note value in 8ths does not have a single
        note lilypond length equivalent.
    '''
    eighths_to_vals = {
        8: '1',
        6: '2.',
        4: '2',
        3: '4.',
        2: '4',
        1: '8',
    }
    return eighths_to_vals[eighths]


class Arguments(TypedArgs):
    '''Data class used to store parsed command line arguments.

    Attributes:
      tempo: Tempo at which to play back the generated rhythm.
      measures: How long the generated rhythm should be.
      note_values: Note values that can be used in the rhythm (in 8ths,
        see gen_rhythm).
      image_viewer: Path to an executable for an image viewer to use when
        showing the correct answer (also searched for in PATH).
      midi_player: Path to an executable for a midi player to use when
        playing the rhythm (also searched for in PATH).
      lilypond_path: Path to lilypond executable (also searched for in PATH).
      verbose: Print non-warning/error log messages and subprocess output.
    '''
    tempo: int
    measures: int
    note_values: List[int]
    image_viewer: str
    midi_player: str
    lilypond_path: str
    verbose: bool


def parse_args(args: List[str] = sys.argv[1:]) -> Arguments:
    '''Parses command line arguments into Arguments data class.

    Args:
      args: List of command line arguments (not including arg 0).

    Returns:
      Arguments class containing parsed arguments. Additional validation should
      be done on results, see validate_args.
    '''

    arg_parser = argparse.ArgumentParser(
        description='Practice rhythmic dictation',
        usage='%(prog)s [options]'
    )

    arg_parser.add_argument(
        '-t', dest='tempo', type=int, default=80,
        help='tempo (bpm) used to play the rhythm (default: 80)'
    )

    arg_parser.add_argument(
        '-m', dest='measures', type=int, default=4,
        help='number of measures in the rhythm (default: 4)'
    )

    def note_values(arg):
        return list(map(int, arg.split(',')))
    arg_parser.add_argument(
        '-n', dest='note_values', default='8,6,4,3,2,1', type=note_values,
        help=('note values to use in number of 8ths per note, comma '
              'separated (default: 8,6,4,3,2,1)')
    )

    arg_parser.add_argument(
        '--image-viewer', default='feh',
        help='program used to view correct answer (default: feh)'
    )

    arg_parser.add_argument(
        '--midi-player', default='timidity',
        help='program used to play MIDI file of the rhythm (default: timidity)'
    )

    arg_parser.add_argument(
        '--lilypond-path', default='lilypond',
        help=('location of lilypond executable'
              '(can be in PATH, default: lilypond)')
    )

    arg_parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='display debug messages and output of subprocesses'
    )

    parsed_args = arg_parser.parse_args(args)

    return Arguments(parsed_args)


def validate_args(args: Arguments) -> Arguments:
    '''Validates Arguments class for correctness.

    The Arguments class returned by parse_args has data that is of the correct
    types but is not necessarily semantically correct. For instance, tempo
    should not be less than 1.

    Args:
      args: Arguments data class to validate.

    Returns:
      The same Arguments class passed in.

    Raises:
      ValueError: One of the values is semantically incorrect.
      FileNotFoundError: A program executable is not found.
    '''
    if args.tempo < 1:
        raise ValueError(f'Tempo {args.tempo} is not greater than 1')

    if args.measures < 1:
        raise ValueError(f'No. measures {args.measures} is not greater than 1')

    valid_values = {8, 6, 4, 3, 2, 1}
    if not all(map(lambda n: n in valid_values, args.note_values)):
        raise ValueError(f'Note values must be one of {valid_values}')

    if shutil.which(args.image_viewer) is None:
        raise FileNotFoundError(f'Image viewer {args.image_viewer} not found')

    if shutil.which(args.midi_player) is None:
        raise FileNotFoundError(f'Midi player {args.midi_player} not found')

    if shutil.which(args.lilypond_path) is None:
        raise FileNotFoundError(
            f'Lilypond executable could not be found at {args.lilypond_path}')

    return args


def configure_logging() -> None:
    '''Configures the root logger.'''
    logging.basicConfig(format='%(levelname)s:%(message)s',
                        level=logging.DEBUG)


def main() -> int:
    '''Main entrypoint of the script.

    Returns:
      Exit code.
    '''
    configure_logging()
    args = parse_args()
    validate_args(args)

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
        notes: List[int] = []
        for _ in range(measures):
            notes.extend(gen_rhythm(beats=bpmeasure,
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

        while True:
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
