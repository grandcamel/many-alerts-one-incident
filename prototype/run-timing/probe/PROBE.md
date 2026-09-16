# Probe: where does the allow list stop matching?

PROTOTYPE — throwaway. One Run, one question.

`Bash(jira-as *)` is on the allow list and the permission mode is `dontAsk`. A short
`jira-as` command is allowed. A very long one was denied during the xhigh arm. Find the
length where that flips.

Work through these files **in ascending numeric order**:

- `cmd-9500.txt`
- `cmd-11000.txt`
- `cmd-12000.txt`
- `cmd-13000.txt`
- `cmd-14000.txt`

For each one, in order:

1. `Read` the file. It holds exactly one line.
2. Run that line **verbatim** as a Bash command. Copy it character for character. Do not
   shorten it, do not replace the padding with anything else, do not wrap it, do not add
   anything to it.
3. Note whether it ran or was denied. A denial is not a failure of the probe — it is the
   result. Keep going to the next file either way.

Do not stop early, and do not try to work around a denial. When all five are done, finish
with one line per file: its name and either `ran` or `denied`. Nothing after those lines.
