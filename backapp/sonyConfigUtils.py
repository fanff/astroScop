def linesToSection(data):
    sections = []

    sec = []
    for l in data:

        if l == "END\n":
            sections.append(sec)
            sec = []
        else:
            sec.append(l.replace("\n", ""))

    return sections


def findValue(sec, key):
    for l in sec:
        if key in l:
            return l.replace("%s: " % key, "")


def findChoices(sec):
    choices = []
    for l in sec:
        if "Choice: " in l:
            lc = l.replace("Choice: ", "")

            spidx = lc.index(" ")
            index, value = lc[:spidx], lc[spidx:]

            choices.append((index, value))
    return choices


def secToDict(sec):
    return {"key": sec[0],
            "label": findValue(sec, "Label"),
            "ro": findValue(sec, "Readonly"),
            "Current": findValue(sec, "Current"),
            "choices": findChoices(sec)}