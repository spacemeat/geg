import sys
import json
import subprocess
from pathlib import Path
from . import ansi

def doShellCommand(cmd):
    print (f"{ansi.lt_black_fg}{cmd}{ansi.all_off}")
    return subprocess.run(cmd, shell=True, check=False, encoding='utf-8', capture_output=True)


def strPath(path):
    return f'{ansi.dk_cyan_fg}{path.parent}/{ansi.lt_cyan_fg}{path.name}{ansi.all_off}'


class Counter:
    def __init__(self, count=0):
        self.count = count
    
    def inc(self):
        self.count += 1


class Issue:
    def __init__(self, errorBlock):
        self.kind = errorBlock['kind']
        self.path = Path(errorBlock['locations'][0]['caret']['file'])
        self.line = errorBlock['locations'][0]['caret']['line']
        self.notes = []
        self.message = errorBlock['message']
        self.opened = False

    def addNote(self, noteBlock):
        self.notes.append(Issue(noteBlock))
    
    def strSelf(self, counter, depth=0):
        src = ''
        if len(self.notes) > 0:
            counter.inc()
            src += f'{counter.count: 4}: {"-" if self.opened else "+"} '
        else:
            src += '        '
        if self.kind == 'error':
            src += f'{ansi.lt_red_fg}   Error{ansi.all_off}: '
        elif self.kind == 'warning':
            src += f'{ansi.lt_yellow_fg}Warning{ansi.all_off}: '
        if self.kind == 'note':
            src += f'{ansi.lt_cyan_fg}    Note{ansi.all_off}: '
        src += f' {strPath(self.path)} ({self.line}): {self.message}\n'

        if self.opened:
            for note in self.notes:
                src += note.strSelf(counter, depth + 1)
        
        return src
    
    def toggle(self, counter, target):
        counter.inc()
        if counter.count == target:
            self.opened = not self.opened
        else:
            for note in self.notes:
                note.toggle(counter, target)

    def __str__(self):
        counter = 0
        return self.strSelf(0)


def main():
    cmd = ' '.join(sys.argv[1:])

    proc = doShellCommand(cmd)
    src = proc.stderr
    if len(src) == 0:
        return

    issuesSrc = json.loads(src)
    issues = []

    print(json.dumps(issuesSrc, indent=4))

    for issueSrc in issuesSrc:
        kind = issueSrc['kind']
        if kind == 'error' or kind == 'warning':
            issues.append(Issue(issueSrc))
        elif kind == 'note':
            issues[-1].addNote(issueSrc)
    
    running = True
    while running:
        c = Counter()
        for iss in issues:
            print (iss.strSelf(c), end='')

        command = input('Command? ').strip()
        if command == 'q':
            break

        try:
            n = int(command)
            nc = Counter()
            for iss in issues:
                iss.toggle(nc, n)
        except:
            print (f'{ansi.dk_red_fg}Type an integer to toggle, or "q" to quit.{ansi.all_off}')