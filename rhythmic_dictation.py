#!/usr/bin/env python3
"""Simple application for practicing rhythmic dictation."""

import argparse
from contextlib import ExitStack
import logging
import pathlib
import random
import shutil
from string import Template
import subprocess
import sys
import tempfile
from typing import Optional, List, Sequence, Tuple
from typed_argparse import TypedArgs  # type: ignore

lilypond_midi_score = Template(
    r"""\version "2.22.2"

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
      \set Staff.midiInstrument = "$midiInstrument"
      \voiceOne
      $notes
    }
  }
  \midi { }
}"""
)

lilypond_layout_score = Template(
    r"""\version "2.22.2"

\paper {
  #(set-paper-size "a6landscape")
}

\score {
  \new Staff {
    \relative a' {
      \tempo 4 = $tempo
      \numericTimeSignature
      \time $timeSignature
      \voiceOne
      $notes
    }
  }
  \layout { }
}"""
)


def gen_rhythm(
    beats: int = 4,
    note_values: Sequence[int] = (16, 12, 8, 6, 4, 2),
) -> Sequence[int]:
    """Generates a rhythm of the given length with the given durations.

    Args:
      beats: Length of the rhythm to generate in quarters (default 4)
      note_values: The durations in 16ths to use when generating the rhythm.
        For instance, a quarter's duration would be 4 (four 16ths).
        (default (16, 12, 8, 6, 4, 2))

    Returns:
      A sequence of durations in 16ths. For example, [2, 6] would be an 8th
      followed by a dotted quarter.

    Raises:
      ValueError: It may not be possible to generate a rhythm of a given
        length given specific durations. If that happens, this error is raised.
    """

    iter_max = 500

    notes = [0]
    sixteenths = beats * 4
    current_sixteenths = 0
    iter_counter = 0
    while current_sixteenths != sixteenths:
        iter_counter += 1
        if iter_counter > iter_max:
            raise ValueError(
                "Given note values cannot create rhythm of the given length"
            )

        current_sixteenths -= notes.pop()

        while current_sixteenths < sixteenths:
            note_val = random.choice(note_values)
            notes.append(note_val)
            current_sixteenths += note_val

    return notes


def sixteenths_to_rests(sixteenths: int) -> Sequence[int]:
    """Splits a note value in sixteenths into valid rest note values.

    Args:
      sixteenths: The note value to split.

    Returns:
      A tuple of the note values of rests that add up to the original note
      value.
    """
    rests = {
        12: (4, 8),
        6: (2, 4),
    }

    if sixteenths in rests:
        return rests[sixteenths]

    return (sixteenths,)


def sixteenths_to_lilypond(sixteenths: int) -> str:
    """Converts from note value in 16ths to lilypond's string representation.

    Args:
      note_values: The note valuein 16ths to convert. For example, a quarter
        note's value would be 4.

    Returns:
      The lilypond string representation of the given note value.

    Raises:
      KeyError: The given note value in 16ths does not have a single
        note lilypond length equivalent.
    """
    sixteenths_to_vals = {
        16: "1",
        12: "2.",
        8: "2",
        6: "4.",
        4: "4",
        2: "8",
        1: "16",
    }
    return sixteenths_to_vals[sixteenths]


class Arguments(TypedArgs):
    """Data class used to store parsed command line arguments.

    Attributes:
      tempo: Tempo at which to play back the generated rhythm.
      measures: How long the generated rhythm should be.
      bpmeasure: How many beats should be in a measure
      note_values: Note values that can be used in the rhythm (in 16ths,
        see gen_rhythm).
      num_rests: The total number of rests to include. If there end up being
        more rests than notes, the generated rhythm will be all rests.
      midi_instrument: MIDI instrument used to play rhythm. See
        https://lilypond.org/doc/v2.22/Documentation/notation/midi-instruments
      image_viewer: Path to an executable for an image viewer to use when
        showing the correct answer (also searched for in PATH).
      midi_player: Path to an executable for a midi player to use when
        playing the rhythm (also searched for in PATH).
      lilypond_path: Path to lilypond executable (also searched for in PATH).
      verbose: Print non-warning/error log messages and subprocess output.
    """

    tempo: int
    measures: int
    bpmeasure: Optional[int]
    note_values: List[int]
    num_rests: int
    midi_instrument: str
    image_viewer: str
    midi_player: str
    lilypond_path: str
    verbose: bool


def parse_args(args: List[str]) -> Arguments:
    """Parses command line arguments into Arguments data class.

    Args:
      args: List of command line arguments (not including arg 0).

    Returns:
      Arguments class containing parsed arguments. Additional validation should
      be done on results, see validate_args.
    """

    arg_parser = argparse.ArgumentParser(
        description="Practice rhythmic dictation", usage="%(prog)s [options]"
    )

    arg_parser.add_argument(
        "-t",
        dest="tempo",
        type=int,
        default=80,
        help="tempo (bpm) used to play the rhythm (default: 80)",
    )

    arg_parser.add_argument(
        "-m",
        dest="measures",
        type=int,
        default=4,
        help="number of measures in the rhythm (default: 4)",
    )
    arg_parser.add_argument(
        "-b",
        dest="bpmeasure",
        type=int,
        help="number of beats in a measure (default: random choice of 2, 3, or 4)",
    )

    def note_values(arg):
        return list(map(int, arg.split(",")))

    arg_parser.add_argument(
        "-n",
        dest="note_values",
        default="16,8,6,4,2",
        type=note_values,
        help=(
            "note values to use in number of 16ths per note, comma "
            "separated (default: 16,8,6,4,2)"
        ),
    )

    arg_parser.add_argument(
        "-r",
        dest="num_rests",
        type=int,
        default=0,
        help=(
            "number of rests to include; if there are more rests than notes, "
            "all notes will be replaced with rests (default: 0)"
        ),
    )

    arg_parser.add_argument(
        "--midi-instrument",
        dest="midi_instrument",
        default="acoustic grand",
        help=(
            "midi instrument used to play rhythm, see: "
            "https://lilypond.org/doc/v2.22/Documentation/notation/midi-instruments "
            " (default: acoustic grand)"
        ),
    )

    arg_parser.add_argument(
        "--image-viewer",
        default="feh",
        help="program used to view correct answer (default: feh)",
    )

    arg_parser.add_argument(
        "--midi-player",
        default="timidity",
        help="program used to play MIDI file of the rhythm (default: timidity)",
    )

    arg_parser.add_argument(
        "--lilypond-path",
        default="lilypond",
        help=("location of lilypond executable" "(can be in PATH, default: lilypond)"),
    )

    arg_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="display debug messages and output of subprocesses",
    )

    parsed_args = arg_parser.parse_args(args)

    return Arguments(parsed_args)


def validate_args(args: Arguments) -> Arguments:
    """Validates Arguments class for correctness.

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
    """
    if args.tempo < 1:
        raise ValueError(f"Tempo {args.tempo} is not greater than 1")

    if args.measures < 1:
        raise ValueError(f"No. measures {args.measures} is not greater than 1")

    if args.bpmeasure is not None and args.bpmeasure < 1:
        raise ValueError(f"No. measures {args.measures} is not greater than 1")

    valid_values = {16, 12, 8, 6, 4, 2, 1}
    if not all(map(lambda n: n in valid_values, args.note_values)):
        raise ValueError(f"Note values must be one of {valid_values}")

    if args.num_rests < 0:
        raise ValueError("Number of rests must be greater than or equal to 0")

    # TODO: probably need to validate args.midi_instrument

    if shutil.which(args.image_viewer) is None:
        raise FileNotFoundError(f"Image viewer {args.image_viewer} not found")

    if shutil.which(args.midi_player) is None:
        raise FileNotFoundError(f"Midi player {args.midi_player} not found")

    if shutil.which(args.lilypond_path) is None:
        raise FileNotFoundError(
            f"Lilypond executable could not be found at {args.lilypond_path}"
        )

    return args


def configure_logging() -> None:
    """Configures the root logger."""
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)


def practice_round(args: Arguments) -> None:
    """Runs a single round of rhythmic dictation practice.

    Args:
      args: Arguments to the program as returned by parse_args
    """
    out = None
    err = None
    if not args.verbose:
        out = subprocess.DEVNULL
        err = subprocess.DEVNULL

    with ExitStack() as exit_stack:
        temp_dir = exit_stack.enter_context(
            tempfile.TemporaryDirectory(prefix="rhythmic_dictation")
        )
        logging.info("Created temporary directory %s", temp_dir)

        layout_score_fn = pathlib.Path(temp_dir) / "layout_score.ly"
        layout_score_file = exit_stack.enter_context(
            open(layout_score_fn, "w", encoding="utf-8")
        )

        logging.info("Created layout lilypond score file %s", layout_score_fn)
        midi_score_fn = pathlib.Path(temp_dir) / "midi_score.ly"
        midi_score_file = exit_stack.enter_context(
            open(midi_score_fn, "w", encoding="utf-8")
        )
        logging.info("Created lilypond score file for MIDI output %s", midi_score_fn)

        if args.bpmeasure is None:
            bpmeasure = random.choice((2, 3, 4))
        else:
            bpmeasure = args.bpmeasure
        measures = args.measures

        logging.info("Generating note durations ...")
        notes: List[int] = []
        for _ in range(measures):
            notes.extend(gen_rhythm(beats=bpmeasure, note_values=args.note_values))

        logging.info("Adding rests ...")
        non_rests = list(range(len(notes)))
        rests = set()
        for _ in range(args.num_rests):
            rest_index = random.choice(non_rests)
            rests.add(rest_index)
            non_rests.remove(rest_index)

        notes_lilypond = []
        for i, note in enumerate(notes):
            if i in rests:
                rest_vals = sixteenths_to_rests(note)
                for val in rest_vals:
                    notes_lilypond.append("r" + sixteenths_to_lilypond(val))
            else:
                notes_lilypond.append("a" + sixteenths_to_lilypond(note))

        notes_lilypond_str = " ".join(notes_lilypond)

        layout_score_string = lilypond_layout_score.substitute(
            tempo=args.tempo, timeSignature=f"{bpmeasure}/4", notes=notes_lilypond_str
        )
        midi_score_string = lilypond_midi_score.substitute(
            tempo=args.tempo,
            timeSignature=f"{bpmeasure}/4",
            notes=notes_lilypond_str,
            midiInstrument=args.midi_instrument,
        )
        layout_score_file.write(layout_score_string)
        layout_score_file.flush()
        midi_score_file.write(midi_score_string)
        midi_score_file.flush()

        logging.info("Converting %s to image ...", layout_score_fn)
        subprocess.run(
            (args.lilypond_path, "--png", layout_score_fn),
            check=True,
            cwd=temp_dir,
            stdout=out,
            stderr=err,
            text=True,
        )
        logging.info("Converting %s to midi ...", midi_score_fn)
        subprocess.run(
            (args.lilypond_path, midi_score_fn),
            check=True,
            cwd=temp_dir,
            stdout=out,
            stderr=err,
            text=True,
        )

        while True:
            logging.info("Playing midi ...")
            subprocess.run(
                (args.midi_player, "midi_score.midi"),
                check=True,
                cwd=temp_dir,
                stdout=out,
                stderr=err,
                text=True,
            )
            again = input("Listen again (y/n)? ")
            if again.lower() == "n":
                break

        logging.info("Showing correct answer")
        try:
            subprocess.run(
                (args.image_viewer, "layout_score.png"),
                check=True,
                cwd=temp_dir,
                stdout=out,
                stderr=err,
                text=True,
            )
        except KeyboardInterrupt:
            pass


def main() -> int:
    """Main entrypoint of the script.

    Returns:
      Exit code.
    """
    configure_logging()
    args = parse_args(sys.argv[1:])
    validate_args(args)

    level = logging.WARNING
    if args.verbose:
        level = logging.DEBUG
    logging.getLogger().setLevel(level)

    while True:
        practice_round(args)

        again = input("Do another (y/n)? ")
        if again.lower() == "n":
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
