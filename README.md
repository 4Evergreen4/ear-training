Rhythm Dictation Practice Utility
=================================

This is a (relatively) simple rhythm dictation practice tool I put together
because I needed to practice rhythmic dictation (big surprise). Right now it
is only capable of generating rhythms in 2/4, 3/4, and 4/4 where the smallest
note is an 8th note and there are no ties between measures. The number of
measures to generate and the BPM is configurable via the command line.

## Running

First, you will need to have `lilypond`, a midi player, and an image viewer
installed. The default midi player is `timidity` and the default image viewer
is `feh`. You can change the paths to all three of these in the command line
options.

Second, you will need to have Python 3.7 at minimum.

Third, clone this repository. Then, create a python virtual env and run
`pip3 install -r requirements` inside the virtual env. Finally, run
`python3 rhythmic_dictation.py` inside the virtual env to run the program.

## Options

See the output of `rhythmic_dictation.py --help`.
