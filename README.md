# protozoid_sq80

Utilities for various tasks related to the Ensoniq SQ-80 synthesizer. Currently, there is only...

## extract_sq80.py

Extract banks/programs from Ensoniq SQ80 disk dump files generated from the
sq80toolkit.

The tool runs in three different modes:

- prog : dump individually saved programs
- bank : dump program banks
- virtbank : dump individual programs consolidated into "virtual banks"

The data is dumped in either pure binary format, or in SYSEX format suitable
for sending directly to the synthesizer over MIDI.

The tool can also be used to generate listings of banks/programs on a disk.

Run with the --help option for usage information.

A blog post with an overview of the tool is [here](https://protozoid.tumblr.com/post/613284464564584448/extracting-ensoniq-sq-80-disk-images).

Thanks and acknowledgements to Rainer Buchty (www.buchty.net) for the
sq80toolkit, and his invaluable work on the SQ80 in general. I have referred to
the source and documentation of the sq80toolkit extensively for the structure
of the disk images.
