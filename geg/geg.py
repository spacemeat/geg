import sys
import os
import json
import subprocess
from pathlib import Path
from . import ansi as a
import shutil
import re
import math
import copy
from enum import Enum
import functools

compileErrorsPath = './.gegstash'

debugLevel = 0
def printDebug(level, string):
    if level <= debugLevel:
        print (string)


codeRegex = re.compile(r'‘[^’]+?’')
operatorRegex = re.compile(r'operator(.+?)\(')
ansiRegex = re.compile(r'\033\[(.*?)m')
akaRegex = re.compile(r' \{aka ‘.*?’\}')
scopedTypeRegex =   re.compile(r'((?:[a-zA-Z0-9_]+::)+)([a-zA-Z0-9_&*.]+)')
scopeLayerRegex =   re.compile(r'([a-zA-Z0-9_]+::)')
templateTypeRegex = re.compile(r'([a-zA-Z0-9_]+)<>::')


def doShellCommand(cmd):
    print (f"{a.Rgb(63, 63, 63).fg()}{cmd}{a.off}")
    return subprocess.run(cmd, shell=True, check=False, encoding='utf-8', capture_output=True)


def strNoColor(string):
    return re.sub(ansiRegex, lambda m: '', string)


def justifyMessage(message, start, width, ribbonColor):
    '''Print the message, with spaces to offset, and spaces to round out the bg color at the end of each line.'''
    src = ''
    chonkLen = width - start - 1
    chonkRemaining = chonkLen

    cursor = 0
    colorBank = 0

    currentColors = ['', '']
    while cursor < len(message):
        if message[cursor:].startswith('\033['):
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
            src += f'{a.off}\n{ribbonColor}    {a.off}{" " * (start - 4)}{currentColors[0]}{currentColors[1]}'
            chonkRemaining = chonkLen

    src += ' ' * chonkRemaining
    src += a.off

    return src


class Style(Enum):
    HIGHLIGHT = 0
    TYPE = 1
    SCOPE = 2
    AKA = 3
    TEMPLATEARGS = 4
    PATH = 5
    DIR = 6
    INVISIBLE = 7
    NOISY = 8
    DIM = 9
    PARAM = 10
    OPERATOR = 11
    CODE = 12

    @staticmethod
    def normalizeStyles(styles):
        if isinstance(styles, list):
            return {s:1 for s in styles}
        elif isinstance(styles, dict):
            return styles
        elif isinstance(styles, Style):
            return {styles:1}
        else:
            raise RuntimeError('Styles must be a dict, list, or Style')

    @staticmethod
    def cascadeStyles(ontoStyles, fromStyles):
        ontoStyles = Style.normalizeStyles(ontoStyles)
        fromStyles = Style.normalizeStyles(fromStyles)

        # these styles don't cascade
        fromStyles.pop(Style.SCOPE, None)
        fromStyles.pop(Style.NOISY, None)
        fromStyles.pop(Style.OPERATOR, None)

        sts = copy.deepcopy(ontoStyles)
        for s, c in fromStyles.items():
            if s in sts:
                sts[s] += c
            else:
                sts[s] = c
        return sts

    @staticmethod
    def getColors(styles):
        styles = Style.normalizeStyles(styles)

        modfgs = [a.Rgb(105, 192, 105),
                  a.Rgb(105, 127, 192),
                  a.Rgb(192, 105, 192),
                  a.Rgb(192, 105, 105),
                  a.Rgb(211, 145, 91),
                  a.Rgb(105, 192, 192)]

        fg = a.Rgb(127, 127, 127)
        bg = a.Rgb(0, 0, 0)

        if Style.CODE not in styles:
            if Style.AKA in styles:
                fg = a.Rgb(71, 31, 71)

            # file
            if Style.PATH in styles:
                fg = a.Rgb(31, 255, 255)
                if Style.DIR in styles:
                    fg = fg.dim()
        else:
            if Style.TYPE not in styles:
                if Style.AKA not in styles:
                    if Style.TEMPLATEARGS in styles:
                        fg = modfgs[styles[Style.TEMPLATEARGS] % 6]
                    elif Style.PARAM in styles:
                        fg = a.Rgb(191, 147, 127)
                    else:
                        fg = a.Rgb(192, 192, 95)
                else:
                    fg = a.Rgb(71, 31, 71)
            else:
                if Style.AKA not in styles and Style.TEMPLATEARGS not in styles:
                    fg = a.Rgb(192, 192, 95)

                elif Style.AKA not in styles and Style.TEMPLATEARGS in styles:
                    fg = modfgs[styles[Style.TEMPLATEARGS] % 6]
                else:
                    fg = a.Rgb(71, 47, 91)

            if Style.OPERATOR in styles:
                fg = fg.dim()

            if Style.SCOPE in styles or Style.NOISY in styles or Style.DIM in styles:
                fg = fg.dim().dim()

        if Style.HIGHLIGHT in styles:
            fg = fg.highlight()

        return (fg.fg(), bg.bg())


def sanitizePath(path, pathOpened):
    if pathOpened:
        m = ModdedString(str(path), [], Style.PATH)
        d = path.parent
        m.modSubstring(0, len(str(d)), Style.DIR)
    else:
        m = ModdedString(str(path.name), [], Style.PATH)
    return m.render()


def sanitizeMessage(message, makeOpened, highlighted):
    sMessage = ''
    for i in range(0, len(message)):
        if message[i] == ' ' and i + 1 < len(message) and message[i + 1] == '>':
            continue
        sMessage += message[i]
    message = sMessage

    cm = a.Rgb(191, 63, 255).fg()
    cs = a.Rgb(255, 255, 255).fg()

    scopeStyle = Style.INVISIBLE
    if makeOpened:
        scopeStyle = Style.SCOPE

    noisyStyle = Style.INVISIBLE
    if makeOpened:
        noisyStyle = Style.NOISY

    akaStyle = Style.INVISIBLE
    if makeOpened:
        akaStyle = Style.AKA

    def rec(nestedString):
        # run until the string stops changing
        refString = ''
        while (nestedString.string != refString):
            refString = nestedString.string

            if (match := codeRegex.search(nestedString.string)):
                newSub = nestedString.modSubstring(match.start() + 1, match.end() - 1, Style.CODE)
                rec(newSub)
                continue

            if (match := akaRegex.search(nestedString.string)):
                if match.end() - match.start() < len(nestedString.string):
                    newSub = nestedString.modSubstring(match.start(), match.end(), akaStyle)
                    rec(newSub)
                    continue

            if match := operatorRegex.search(nestedString.string):
                newSub = nestedString.modSubstring(match.start() + len('operator'), match.end() - 1, Style.OPERATOR)
                rec(newSub)
                continue

            if (tn := nestedString.string.find('typename ')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('typename '), Style.INVISIBLE)
                continue

            if (tn := nestedString.string.find('template')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('template'), Style.TYPE)
                continue

            def findPairOf(startCh, endCh, styles={}):
                lessPos = -1
                for i, ch in enumerate(nestedString.string):
                    if ch == startCh:
                        if i < len(nestedString.string) - 1 and nestedString.string[i + 1] != endCh:
                            lessPos = i
                    if ch == endCh and lessPos > -1 and i > 0 and nestedString.string[i - 1] != startCh:
                        newSub = nestedString.modSubstring(lessPos + 1, i, styles)
                        rec(newSub)
                        return True
                return False
            
            def findPairOf2(startSeq, endSeq, styles={}):
                sn = len(nestedString.string)
                while sn >= 0:
                    if (sn := nestedString.string[:sn].rfind(startSeq)) >= 0:
                        en = nestedString.string[sn + len(startSeq):].find(endSeq) + sn + len(startSeq)
                        if en > sn and (sn > 0 or en < len(nestedString.string) - 1):
                            newSub = nestedString.modSubstring(sn, en + 1, styles)
                            rec(newSub)
                            return True
                return False


            if findPairOf('<', '>', Style.TEMPLATEARGS):
                continue

            if findPairOf('(', ')', Style.PARAM):
                continue

            if findPairOf('[', ']'):
                continue

            if findPairOf('{', '}'):
                continue

            def findCommas():
                for i, ch in enumerate(nestedString.string):
                    if ch == ',':
                        if i > 0:
                            newSub = nestedString.modSubstring(0, i)
                            rec(newSub)
                            return True
                        elif len(nestedString.string) > 1:
                            newSub = nestedString.modSubstring(i + 1, len(nestedString.string))
                            rec(newSub)
                            return True
                return False

            if findCommas():
                continue

            if findPairOf2('allocator<', '>', Style.DIM):
                continue

            if findPairOf2('char_traits<', '>', Style.DIM):
                continue

            if (tn := nestedString.string.find('basic_')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('basic_'), Style.DIM)
                continue

            if (tn := nestedString.string.find('const ')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('const '), Style.DIM)
                continue

            if (tn := nestedString.string.find('class ')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('class '), Style.DIM)
                continue

            if (tn := nestedString.string.find('struct ')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('class '), Style.DIM)
                continue

            match = scopedTypeRegex.search(nestedString.string)
            if match and not nestedString.string.endswith('::'):
                scopeStr = match.group(1)
                typeStr = match.group(2)

                newSub = nestedString.modSubstring(match.start(), match.end(), Style.TYPE)
                newSub2 = newSub.modSubstring(0, len(scopeStr), scopeStyle)
                rec(newSub)
                rec(newSub2)
                continue

            match = templateTypeRegex.search(nestedString.string)
            if match:
                newSub = nestedString.modSubstring(match.start(), match.end() - 2, Style.TYPE)
                rec(newSub)
                continue

            if (tn := nestedString.string.find('<>')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('<>'))
                continue

            if (tn := nestedString.string.find('()')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('()'), [Style.PARAM, Style.OPERATOR])
                continue

            if (tn := nestedString.string.find('::type')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('::type'), [noisyStyle, Style.TYPE])
                continue

            if (tn := nestedString.string.find('::value')) >= 0:
                newSub = nestedString.modSubstring(tn, tn + len('::value'), [noisyStyle, Style.TYPE])
                continue

            match = scopeLayerRegex.search(nestedString.string)
            if match and match.end() - match.start() < len(nestedString.string):
                newSub = nestedString.modSubstring(match.start(), match.end(), scopeStyle)
                rec(newSub)
                continue

            if nestedString.string.startswith('::') and len(nestedString.string) > 2:
                newSub = nestedString.modSubstring(0, 2)
                continue

            if nestedString.string.startswith(' ') and len(nestedString.string) > 1:
                newSub = nestedString.modSubstring(0, 1)
                continue

            if nestedString.string.endswith(' ') and len(nestedString.string) > 1:
                newSub = nestedString.modSubstring(len(nestedString.string) - 1, len(nestedString.string))
                continue

            if nestedString.string.startswith('_') and len(nestedString.string) > 1:
                newSub = nestedString.modSubstring(0, 1, noisyStyle)
                continue

            if nestedString.string.endswith('_') and len(nestedString.string) > 1:
                newSub = nestedString.modSubstring(len(nestedString.string) - 1, len(nestedString.string), noisyStyle)
                continue

            if (tn := nestedString.string.find('&&')) >= 0 and len(nestedString.string) > 2:
                newSub = nestedString.modSubstring(tn, tn + len('&&'), Style.OPERATOR)
                continue

            if (tn := nestedString.string.find('&')) >= 0 and len(nestedString.string) > 1:
                newSub = nestedString.modSubstring(tn, tn + len('&'), Style.OPERATOR)
                continue

            if (tn := nestedString.string.find('*')) >= 0 and len(nestedString.string) > 1:
                newSub = nestedString.modSubstring(tn, tn + len('*'), Style.OPERATOR)
                continue

    ns = ModdedString(message, [], Style.HIGHLIGHT if highlighted else {})
    rec(ns)
    return ns


class ModdedString:
    def __init__(self, strings, mods = [], styles = {}):
        cm = a.Rgb(192, 192, 192).fg()
        cs = a.Rgb(192, 192, 92).fg()

        if isinstance(strings, list):
            self.strings = strings
        elif isinstance(strings, str):
            self.strings = [strings]
        else:
            raise RuntimeError(f'"strings" must be a list of strings or a string.')

        if isinstance(mods, list):
            self.mods = mods
        elif isinstance(mods, ModdedString):
            self.mods = [mods]
        else:
            raise RuntimeError(f'"mods" must be a list of ModdedStrings or a ModdedString.')

        if len(self.strings) - len(self.mods) != 1:
            raise RuntimeError(f'There should be one more string than mod.')

        self.styles = Style.normalizeStyles(styles)


    def reprRec(self, depth = 0):
        cm = a.Rgb(192, 192, 192).fg()
        cs = a.Rgb(255, 157, 184).fg()
        src = ''
        src += f'{cm}{"- " * depth}children: {cs}{len(self.mods)}\n'
        src += f'{cm}{"- " * depth}styles: {cs}{"|".join([s.name for s in self.styles])}\n'
        src += ''.join([f'{cm}{"- " * depth}\'{cs}{s}{cm}\'\n' for s in self.strings])
        src += f'{a.off}\n'
        for n in self.mods:
            src += n.reprRec(depth + 1)

        return src


    def __repr__(self):
        return self.reprRec()


    def modSubstring(self, start, end, styles={}):
        assert(start >= 0 and start < len(self.string))
        assert(end > 0 and end <= len(self.string) and start < end)

        cm = a.Rgb(63, 63, 255).fg()
        ch = a.Rgb(192, 143, 127).fg()
        cs = a.Rgb(127, 255, 127).fg()

        styles = Style.normalizeStyles(styles)

        printDebug (1, f'{cm}DisplaceSubStr: start: {start}; end: {end}; from: \'{cs}{self.string[0:start]}{ch}{self.string[start:end]}{cs}{self.string[end:]}{cm}\' as {"|".join([s.name for s in styles.keys()])}{a.off}')
        printDebug (2, f'{cm}     Top self is:\n{a.off}{self}')

        removals = []
        newStrings = []
        newMods = []
        totalLen = 0
        strStart = -1
        strEnd = -1
        newStrL = None
        newStrR = None
        for i, s in enumerate(self.strings):
            if strStart < 0 and start >= totalLen and start < totalLen + len(s):
                strStart = i
                newStrL = (s[:start - totalLen], s[start - totalLen : end - totalLen])
            if end >= totalLen and end <= totalLen + len(s):
                strEnd = i
                if strStart == strEnd:
                    newStrR = (0, s[end - totalLen:])
                else:
                    newStrR = (s[:end - totalLen], s[end - totalLen:])
            totalLen += len(s)

        assert(strStart >= 0)
        assert(strEnd >= strStart)

        for i in range(strStart, strEnd):
            removals.append(self.mods[i])

        newStrings = [newStrL[1]]
        for i, r in enumerate(reversed(removals)):
            if i < len(removals) - 1:
                newStrings.append(self.strings[strStart + i + 1])
            newMods.append(r)
        if len(removals) > 0:
            newStrings.append(newStrR[0])

        assert(len(newStrings) - len(newMods) == 1)

        newMods.reverse()
        m = ModdedString(newStrings, newMods, styles)

        if strEnd == strStart:
            self.strings[strStart] = newStrR[1]
            self.strings.insert(strStart, newStrL[0])
        elif strEnd - strStart == 1:
            self.strings[strStart] = newStrL[0]
            self.strings[strEnd] = newStrR[1]
        else:
            self.strings[strStart] = newStrL[0]
            self.strings[strEnd] = newStrR[1]
            for i in range(strStart + 1, strEnd):
                del self.strings[strStart + 1]

        if strEnd == strStart:
            self.mods.insert(strStart, m)
        elif strEnd - strStart == 1:
            self.mods[strStart] = m
        else:
            self.mods[strStart] = m
            for i in range(strStart + 1, strEnd):
                del self.mods[strStart + 1]

        printDebug (2, f'{cm}     Now self is:\n{a.off}{self}')
        assert(len(self.strings) - len(self.mods) == 1)

        return m


    @property
    def string(self):
        return ''.join(self.strings)


    def render(self, styles={}):
        src = ''

        styles = Style.normalizeStyles(styles)

        cascadedStyles = Style.cascadeStyles(self.styles, styles)
        fg, bg = Style.getColors(cascadedStyles)

        if Style.INVISIBLE not in cascadedStyles:
            for s, m in zip(self.strings, self.mods):
                if len(s) > 0:
                    src += f'{fg}{bg}{s}'
                src += m.render(cascadedStyles)
            src += f'{fg}{bg}{self.strings[-1]}'

        return src


class Counter:
    def __init__(self, count=0):
        self.count = count

    def inc(self):
        self.count += 1


class Issue:
    def __init__(self, issueBlock):
        self.kind = issueBlock['kind']
        self.path = Path(issueBlock['locations'][0]['caret']['file']).resolve()
        self.line = issueBlock['locations'][0]['caret']['line']
        self.children = [Issue(chBlock) for chBlock in issueBlock.get('children', [])]
        self.notes = []
        self.message = issueBlock['message']
        self.issueOpened = False
        self.pathOpened = False
        self.messageOpened = False


    def addNote(self, noteBlock):
        self.notes.append(Issue(noteBlock))


    def render(self, issueCounter, pathCounter, topIssueCounter, depth=0):
        termWidth, _ = shutil.get_terminal_size((80, 20))

        src = ''

        if depth == 0:
            topIssueCounter.inc()

        bgColor = f'{a.Rgb(0, 31, 0).bg() if topIssueCounter.count % 2 == 1 else a.Rgb(0, 0, 31).bg()}'

        if len(self.notes) + len(self.children) > 0:
            issueCounter.inc()
            src += f'{bgColor}{issueCounter.count:}: {"-" if self.issueOpened else "+"}{a.off} '
        else:
            src += f'{bgColor}    {a.off} '

        if self.kind == 'error':
            src += f'{a.Rgb(255, 0, 0).fg()} Err: '
        elif self.kind == 'warning':
            src += f'{a.Rgb(255, 255, 0).fg()}Warn: '
        if self.kind == 'note':
            src += f'{a.Rgb(0, 255, 255).fg()}Note: '

        pathCounter.inc()
        if self.pathOpened:
            src += f'{a.Rgb(255, 255, 255).fg()}'
        else:
            src += f'{a.Rgb(127, 127, 127).fg()}'
        src += f'{" " if depth > 0 else ""}{a.Rgb(31, 255, 255).dim().fg()}p{pathCounter.count}:{" " if depth == 0 else ""} '
        src += f'{sanitizePath(self.path, self.pathOpened)}'
        src += f' {a.Rgb(0, 127, 127).fg()}({self.line}): '

        if self.messageOpened:
            src += f'{a.Rgb(255, 255, 255).fg()}'
        else:
            src += f'{a.Rgb(127, 127, 127).fg()}'
        src += f'm{pathCounter.count}: '

        msg = sanitizeMessage(self.message, self.messageOpened, depth == 0 and self.issueOpened)
        msg = justifyMessage(msg.render(), len(strNoColor(src)), termWidth, bgColor)
        src += f'{msg}'

        src += f'{a.off}\n'

        if self.issueOpened:
            for ch in self.children:
                src += ch.render(issueCounter, pathCounter, topIssueCounter, depth + 1)
            for note in self.notes:
                src += note.render(issueCounter, pathCounter, topIssueCounter, depth + 1)

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


    def toggleAllIssues(self):
        self.issueOpened = not self.issueOpened
        for ch in self.children:
            ch.toggleAllIssues()
        for note in self.notes:
            note.toggleAllIssues()


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


    def toggleAllPaths(self):
        self.pathOpened = not self.pathOpened
        for ch in self.children:
            ch.toggleAllPaths()
        for note in self.notes:
            note.toggleAllPaths()


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


    def toggleAllMessages(self):
        self.messageOpened = not self.messageOpened
        for ch in self.children:
            ch.toggleAllMessages()
        for note in self.notes:
            note.toggleAllMessages()


    def __str__(self):
        counter = 0
        return self.render(0)


def printDivision():
    termWidth, _ = shutil.get_terminal_size((80, 20))
    for i in range(0, termWidth):
        y = int(math.sin(2 * math.pi  * i / termWidth * 3) * 255.0)
        if y < 0:
            print (a.Rgb(0, 0, -y).fg(), end='')
        else:
            print (a.Rgb(0, y, 0).fg(), end='')
        print ('-', end='')

    print (a.off)


def main():
    #src = sys.stdin.read()
    #if len(src) == 0:
    #    return

    src = ''
    go = True

    if not os.path.exists(compileErrorsPath):
        print ('No compile errors.')
        return 0

    f = open(compileErrorsPath)

    while go:
        #l = sys.stdin.readline()
        l = f.readline()
        if l == 'END_OF_ERR\n':
            go = False
        else:
            src += l
            #src += '\n'

    endl = '\n'

    stuff = ",".join([f"{s}" for s in src.strip().split(endl) if len(s) > 0])

    fsrc = f'[{stuff}]'

    try:
        issuesSrc = json.loads(fsrc)
    except:
        print(fsrc)
        quit()

    issues = []

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
            print (iss.render(ec, pc, tc), end='')

        command = ''
        while True:
            command = input(f'{a.off}Command? ').strip()

            if len(command) == 0:
                continue

            elif command == 's':
                break

            elif command == 'q':
                running = False
                break

            elif command == '*':
                for iss in issues:
                    iss.toggleAllIssues()
                break

            elif str.isdigit(command):
                n = int(command)
                ec = Counter()
                for iss in issues:
                    iss.toggleIssue(ec, n)
                break

            elif command[0] == 'p':
                if command[1:] == '*':
                    for iss in issues:
                        iss.toggleAllPaths()
                elif str.isdigit(command[1:]):
                    n = int(command[1:])
                    pc = Counter()
                    for iss in issues:
                        iss.togglePath(pc, n)
                break

            elif command[0] == 'm':
                if command[1:] == '*':
                    for iss in issues:
                        iss.toggleAllMessages()
                elif str.isdigit(command[1:]):
                    n = int(command[1:])
                    pc = Counter()
                    for iss in issues:
                        iss.toggleMessage(pc, n)
                break

            else:
                print (f'''{a.Rgb(192, 0, 0).fg()}Type an integer to open/close an issue,
     "*" to open/close all issues,
     "p" and an integer to expand/contract a path, or "*" to expand/contract all paths,
     "m" and an integer to expand/contract a message, or "*" to expand/contract all messages,
  or "q" to quit.{a.off}''')
    
    return 0
