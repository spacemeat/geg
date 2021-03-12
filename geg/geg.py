import sys
import json
import subprocess
from pathlib import Path
from . import ansi
import shutil
import re
import math
from enum import Enum
import functools


ansiRegex = re.compile(r'\033\[(.*?)m')
akaRegex = re.compile(r'\{aka ‘(.*?)’\}')
scopeRegex = re.compile(r'([a-zA-Z0-9_]+::)+')
typeRegex = re.compile(r'‘(.*?)’')
templateArgsRegex = re.compile(r'<(.*?)>')  # might not work nested


def doShellCommand(cmd):
    print (f"{ansi.lt_black_fg}{cmd}{ansi.all_off}")
    return subprocess.run(cmd, shell=True, check=False, encoding='utf-8', capture_output=True)


def strPath(path, pathOpened):
    if pathOpened:
        m = HierString(str(path), Style.PATH)
        d = path.parent
        m.markSubStr(0, len(str(d)), Style.DIR)
    else:
        m = HierString(str(path.name), Style.PATH)
    return m.render()


def strNoColor(string):
    return re.sub(ansiRegex, lambda m: '', string)


def sanitizeMessage(message, makeOpened, highlighted):
    m = HierString(message, Style.HIGHLIGHT if highlighted else {})

    # remove 'aka' bits
    if makeOpened:
        for match in akaRegex.finditer(message):
            #print (f'Found aka: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.AKA)
    else:
        for match in akaRegex.finditer(message):
            #print (f'Found aka: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.INVISIBLE)

    if makeOpened:
        for match in scopeRegex.finditer(message):
            #print (f'Found scope: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.SCOPE)
    else:
        for match in scopeRegex.finditer(message):
            #print (f'Found scope: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.INVISIBLE)

    for match in typeRegex.finditer(message):
        #print (f'Found type: {match.start()} - {match.end()}')
        m.markSubStr(match.start(), match.end(), Style.TYPE)

    return m.render()


def justifyMessage(message, start, width, fgColor, bgColor):
    '''Print the message, with spaces to offset, and spaces to round out the bg color at the end of each line.'''
    src = ''
    chonkLen = width - start - 1
    chonkRemaining = chonkLen

    cursor = 0
    colorBank = 0

    currentColors = ['', '']
    while cursor < len(message):
        if message[cursor:].startswith('\033['):
            #breakpoint()
            colorStart = cursor
            cursor += len('\033[')
            while message[cursor] != 'm':
                cursor += 1
            cursor += 1
            colorEnd = cursor
            currentColors[colorBank] = message[colorStart:colorEnd]
            src += currentColors[colorBank]
            colorBank = 1 - colorBank
        else:
            src += message[cursor]
            chonkRemaining -= 1
            cursor += 1

        if chonkRemaining == 0 and cursor < len(message):
            src += f'{ansi.all_off}\n{bgColor}    {ansi.all_off}{" " * (start - 4)}{currentColors[0]}{currentColors[1]}'
            chonkRemaining = chonkLen

    src += ' ' * chonkRemaining
    src += ansi.all_off

    return src


class Arjeeby:
    def __init__(self, r = 0, g = 0, b = 0):
        self.r = r
        self.g = g
        self.b = b
    
    def fg(self):
        return ansi.rgb_fg(int(self.r), int(self.g), int(self.b))

    def bg(self):
        return ansi.rgb_bg(int(self.r), int(self.g), int(self.b))
    
    def highlight(self):
        return Arjeeby(min(self.r * 2, 255), min(self.g * 2, 255), min(self.b * 2, 255))

    def dim(self):
        return Arjeeby(self.r / 2, self.g / 2, self.b / 2)
        #return Arjeeby(max(self.r - 63, 0), max(self.g - 63, 0), max(self.b - 63, 0))


class Style(Enum):
    HIGHLIGHT = 0
    TYPE = 1
    SCOPE = 2
    AKA = 3
    TEMPLATEARGS = 4
    PATH = 5
    DIR = 6
    INVISIBLE = 7

    @staticmethod
    def getColors(styles):
        fg = Arjeeby(127, 127, 127)
        bg = Arjeeby(0, 0, 0)

        if Style.TYPE not in styles:
            if Style.AKA not in styles:
                fg = Arjeeby(127, 127, 127)
            else:
                fg = Arjeeby(71, 31, 71)

            # file
            if Style.PATH in styles:
                fg = Arjeeby(31, 255, 255)
                if Style.DIR in styles:
                    fg = fg.dim()
        else:
            if Style.AKA not in styles:
                fg = Arjeeby(127, 127, 63)
                if Style.SCOPE in styles:
                    fg = fg.dim().dim()
            else:
                fg = Arjeeby(71, 47, 91)
                if Style.SCOPE in styles:
                    fg = fg.dim().dim()

        if Style.HIGHLIGHT in styles:
            fg = fg.highlight()

        return (fg.fg(), bg.bg())


class SubStr:
    def __init__(self, start, end, styles):
        self.start = start
        self.end = end
        self.styles = styles
    
    def __repr__(self):
        return f'start: {self.start}; end: {self.end}'


class HierString:
    def __init__(self, initStr, styles={}):
        self.string = initStr
        if type(styles) is list:
            styles = {s: None for s in styles}
        elif type(styles) is Style:
            styles = {styles: None}
        if len(styles) > 0:
            self.subStrs = [SubStr(0, len(initStr), styles)]
        else:
            self.subStrs = [SubStr(0, len(initStr), {})]

    def markSubStr(self, start, end, styles):
        assert(start <= end)
        assert(start >= 0)
        assert(end <= len(self.string))

        if type(styles) is list:
            styles = {s: None for s in styles}
        elif type(styles) is Style:
            styles = {styles: None}
        self.subStrs.append(SubStr(start, end, styles))
    
    def render(self):
        def compare(a, b):
            if a.start < b.start:
                return -1
            elif a.start == b.start and a.end > b.end:
                return -1
            elif a.start == b.start and a.end < b.end:
                return 1
            elif a.start > b.start:
                return 1
            else:
                return 0

        subStrs = sorted(self.subStrs, key=functools.cmp_to_key(compare))

        #for s in subStrs:
        #    print(s)

        src = ''
        cur = 0
        subStrCur = 0

        subStrStack = [subStrs[0]]
        styleStack = [subStrs[0].styles]

        #breakpoint()

        while len(subStrStack) > 0:
            sub = subStrStack[-1]
            #print (f'cur = {cur}')
            #print (f'subStrCur = {subStrCur}')
            #print (f'Using sub #{len(subStrStack) - 1}')
            lenToThisEnd = sub.end - cur
            #print (f'lenToThisEnd = {lenToThisEnd}')
            lenToNextStart = lenToThisEnd + 1
            if len(subStrs) > subStrCur + 1:
                lenToNextStart = subStrs[subStrCur + 1].start - cur
            #print (f'lenToNextStart = {lenToNextStart}')
            amt = min(lenToThisEnd, lenToNextStart)

            # print the current text in the current style
            if amt > 0:
                fg, bg = Style.getColors(styleStack[-1])
                if Style.INVISIBLE not in styleStack[-1]:
                    src += f'{fg}{bg}'
                    src += self.string[cur : cur + amt]
                #print (f'Printing style #{len(styleStack) - 1}')
                #print (f'Printing string: {self.string[cur : cur + amt]}')
                cur += amt

            # if we're closing a style before we open the next one,
            if lenToThisEnd < lenToNextStart:
                subStrStack.pop()
                styleStack.pop()
                #print (f'Popping stack; now len = {len(styleStack)}')
            else:
                subStrCur += 1
                subStrStack.append(subStrs[subStrCur])
                styles = {**styleStack[-1], **subStrs[subStrCur].styles}
                styleStack.append(styles)
                #print (f'Pushing stack; now len = {len(styleStack)}')

        return src


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
        self.children = [Issue(chBlock) for chBlock in errorBlock.get('children', [])]
        self.notes = []
        self.message = errorBlock['message']
        self.issueOpened = False
        self.pathOpened = False
        self.messageOpened = False


    def addNote(self, noteBlock):
        self.notes.append(Issue(noteBlock))

        
    def strSelf(self, issueCounter, pathCounter, topIssueCounter, depth=0):
        termWidth, _ = shutil.get_terminal_size((80, 20))

        src = ''

        if depth == 0:
            topIssueCounter.inc()
        
        bgColor = f'{ansi.dk_orange_bg if topIssueCounter.count % 2 == 1 else ansi.dk_blue_bg}'

        if len(self.notes) + len(self.children) > 0:
            issueCounter.inc()
            src += f'{bgColor}{issueCounter.count:}: {"-" if self.issueOpened else "+"}{ansi.all_off} '
        else:
            src += f'{bgColor}    {ansi.all_off} '

        if self.kind == 'error':
            src += f'{ansi.lt_red_fg} Err: '
        elif self.kind == 'warning':
            src += f'{ansi.lt_yellow_fg}Warn: '
        if self.kind == 'note':
            src += f'{ansi.lt_cyan_fg}Note: '

        pathCounter.inc()
        if self.pathOpened:
            src += f'{ansi.lt_white_fg}'
        else:
            src += f'{ansi.dk_white_fg}'
        src += f'{" " if depth > 0 else ""}p{pathCounter.count}:{" " if depth == 0 else ""} '
        src += f'{strPath(self.path, self.pathOpened)}'
        src += f' {ansi.dk_cyan_fg}({self.line}): '

        if self.messageOpened:
            src += f'{ansi.lt_white_fg}'
        else:
            src += f'{ansi.dk_white_fg}'
        src += f'm{pathCounter.count}: '

        fgColor = f'{ansi.lt_white_fg if depth == 0 else ansi.dk_white_fg}'
        msg = sanitizeMessage(self.message, self.messageOpened, depth == 0 and self.issueOpened)
        msg = justifyMessage(msg, len(strNoColor(src)), termWidth, fgColor, bgColor)
        src += f'{msg}'

        src += f'{ansi.all_off}\n'

        if self.issueOpened:
            for ch in self.children:
                src += ch.strSelf(issueCounter, pathCounter, topIssueCounter, depth + 1)
            for note in self.notes:
                src += note.strSelf(issueCounter, pathCounter, topIssueCounter, depth + 1)
        
        return src

    
    def toggleIssue(self, counter, target):
        if len(self.notes) + len(self.children) > 0:
            counter.inc()
        if counter.count == target:
            self.issueOpened = not self.issueOpened
        else:
            if self.issueOpened:
                for ch in self.children:
                    ch.toggleIssue(counter, target)
                for note in self.notes:
                    note.toggleIssue(counter, target)


    def togglePath(self, counter, target):
        counter.inc()
        if counter.count == target:
            self.pathOpened = not self.pathOpened
        else:
            if self.issueOpened:
                for ch in self.children:
                    ch.togglePath(counter, target)
                for note in self.notes:
                    note.togglePath(counter, target)


    def toggleMessage(self, counter, target):
        counter.inc()
        if counter.count == target:
            self.messageOpened = not self.messageOpened
        else:
            if self.issueOpened:
                for ch in self.children:
                    ch.toggleMessage(counter, target)
                for note in self.notes:
                    note.toggleMessage(counter, target)


    def __str__(self):
        counter = 0
        return self.strSelf(0)


def printDivision():
    termWidth, _ = shutil.get_terminal_size((80, 20))
    for i in range(0, termWidth):
        y = int(math.sin(2 * math.pi  * i / termWidth * 3) * 255.0)
        if y < 0:
            print (f'\033[38;2;0;0;{-y}m', end='')
        else:
            print (f'\033[38;2;0;{y};0m', end='')
        print ('-', end='')
    print (ansi.all_off)


def main():
    cmd = ' '.join(sys.argv[1:]) + ' -fdiagnostics-format=json'

    proc = doShellCommand(cmd)
    src = proc.stderr
    if len(src) == 0:
        print (proc.stdout)
        return

    endl = '\n'
    #print(src)
    #print ('   -----     -----     -----')
    fsrc = f'[{",".join([f"{s}" for s in src.strip().split(endl)])}]'
    #print(fsrc)

    try:
        issuesSrc = json.loads(fsrc)
    except:
        print(src)
        quit()

    issues = []

    #print ('   -----     -----     -----')
    #print(json.dumps(issuesSrc, indent=4))
    #print ('   -----     -----     -----')

    for issueSrcList in issuesSrc:
        for issueSrc in issueSrcList:
            kind = issueSrc['kind']
            if kind == 'error' or kind == 'warning':
                issues.append(Issue(issueSrc))
            elif kind == 'note':
                issues[-1].addNote(issueSrc)
            else:
                issues.append(Issue(issueSrc))
    
    running = len(issues) > 0
    while running:
        ec = Counter()
        pc = Counter()
        tc = Counter()
        printDivision()
        for iss in issues:
            print (iss.strSelf(ec, pc, tc), end='')

        command = ''
        while True:
            command = input(f'{ansi.all_off}Command? ').strip()
        
            if len(command) == 0:
                continue

            elif command == 'q':
                running = False
                break

            elif str.isdigit(command):
                n = int(command)
                ec = Counter()
                for iss in issues:
                    iss.toggleIssue(ec, n)
                break

            elif command[0] == 'p' and str.isdigit(command[1:]):
                n = int(command[1:])
                pc = Counter()
                for iss in issues:
                    iss.togglePath(pc, n)
                break

            elif command[0] == 'm' and str.isdigit(command[1:]):
                n = int(command[1:])
                pc = Counter()
                for iss in issues:
                    iss.toggleMessage(pc, n)
                break

            else:
                print (f'{ansi.dk_red_fg}Type an integer to open/close an issue, or "p" and an integer to expand a path, or "q" to quit.{ansi.all_off}')