import sys
import json
import subprocess
from pathlib import Path
from . import ansi
import shutil
import re
import math
import copy
from enum import Enum
import functools


operatorRegex = re.compile(r'operator(.+?)\(')
ansiRegex = re.compile(r'\033\[(.*?)m')
akaRegex = re.compile(r'\{aka ‘(.*?)’\}')
#scopeRegex = re.compile(r'([a-zA-Z0-9_<>&*]+::)+')
#typeRegex = re.compile(r'‘(.*?)’')
scopedTypeRegex =   re.compile(r'((?:[a-zA-Z0-9_]+::)+)([a-zA-Z0-9_&*.]+)')
scopeLayerRegex =   re.compile(r'([a-zA-Z0-9_]+::)')
templateTypeRegex = re.compile(r'([a-zA-Z0-9_]+)<>::')
underscoredRegex =  re.compile(r'_+([a-zA-Z0-9_]+?)_+$')


def doShellCommand(cmd):
    print (f"{ansi.rgb_fg(63, 63, 63)}{cmd}{ansi.all_off}")
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
    sMessage = ''
    for i in range(0, len(message)):
        if message[i] == ' ' and len(message) < i + 1 and message[i + 1] == '>':
            i += 1
        sMessage += message[i]
    sMessage = message
    m = HierString(sMessage, Style.HIGHLIGHT if highlighted else {})

    # remove 'aka' bits
    if makeOpened:
        for match in akaRegex.finditer(sMessage):
            #print (f'Found aka: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.AKA)
    else:
        for match in akaRegex.finditer(sMessage):
            #print (f'Found aka: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.INVISIBLE)

    if makeOpened:
        for match in scopeRegex.finditer(sMessage):
            #print (f'Found scope: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.SCOPE)
    else:
        for match in scopeRegex.finditer(sMessage):
            #print (f'Found scope: {match.start()} - {match.end()}')
            m.markSubStr(match.start(), match.end(), Style.INVISIBLE)

    for match in typeRegex.finditer(sMessage):
        #print (f'Found type: {match.start()} - {match.end()}')
        m.markSubStr(match.start(), match.end(), Style.TYPE)

    return m.render()


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
            src += f'{ansi.all_off}\n{ribbonColor}    {ansi.all_off}{" " * (start - 4)}{currentColors[0]}{currentColors[1]}'
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
    def combineStyles(aStyles, bStyles):
        aStyles = Style.normalizeStyles(aStyles)
        bStyles = Style.normalizeStyles(bStyles)

        sts = copy.deepcopy(aStyles)
        for s, c in bStyles.items():
            if s in sts:
                sts[s] += c
            else:
                sts[s] = c
        return sts

    @staticmethod
    def getColors(styles):
        fg = Arjeeby(127, 127, 127)
        bg = Arjeeby(0, 0, 0)

        if Style.TYPE not in styles:
            if Style.AKA not in styles:
                if Style.TEMPLATEARGS in styles:
                    if styles[Style.TEMPLATEARGS] % 2 == 0:
                        fg = Arjeeby(192, 95, 192)
                    else:
                        fg = Arjeeby(95, 127, 211)
                elif Style.PARAM in styles:
                    fg = Arjeeby(191, 147, 127)
                else:
                    fg = Arjeeby(127, 127, 127)
            else:
                fg = Arjeeby(71, 31, 71)

            # file
            if Style.PATH in styles:
                fg = Arjeeby(31, 255, 255)
                if Style.DIR in styles:
                    fg = fg.dim()
        else:
            if Style.AKA not in styles and Style.TEMPLATEARGS not in styles:
                fg = Arjeeby(192, 192, 95)

            elif Style.AKA not in styles and Style.TEMPLATEARGS in styles:
                #breakpoint()
                if styles[Style.TEMPLATEARGS] % 2 == 0:
                    fg = Arjeeby(192, 95, 192)
                else:
                    fg = Arjeeby(95, 127, 211)
            else:
                fg = Arjeeby(71, 47, 91)

        if Style.SCOPE in styles or Style.NOISY in styles or Style.DIM in styles:
            fg = fg.dim().dim()

        if Style.OPERATOR in styles:
            fg = fg.dim()

        if Style.HIGHLIGHT in styles:
            fg = fg.highlight()

        return (fg.fg(), bg.bg())


def sanitizeString(message, makeOpened, highlighted):
    sMessage = ''
    for i in range(0, len(message)):
        if message[i] == ' ' and i + 1 < len(message) and message[i + 1] == '>':
            continue
        sMessage += message[i]
    message = sMessage

    cm = ansi.rgb_fg(191, 63, 255)
    cs = ansi.rgb_fg(255, 255, 255)

    scopeStyle = ''
    if makeOpened:
        scopeStyle = Style.SCOPE
    else:
        scopeStyle = Style.INVISIBLE

    noisyStyle = ''
    if makeOpened:
        noisyStyle = Style.NOISY
    else:
        noisyStyle = Style.INVISIBLE

    def rec(nestedString):
        #print (f'{ansi.rgb_fg(192, 192, 192)}rec -     string: {ansi.rgb_fg(192, 122, 192)}{nestedString.string}')
        # run until the string stops changing
        refString = ''
        while (nestedString.string != refString):
            refString = nestedString.string

            akaStyle = Style.INVISIBLE
            if makeOpened:
                akaStyle = Style.AKA

            if (match := akaRegex.search(nestedString.string)):
                if match.end() - match.start() < len(nestedString.string):
                    #print (f'Found aka: {match.start()} - {match.end()}')
                    newSub = nestedString.markSubStr(match.start(), match.end(), akaStyle)
                    rec(newSub)
                    continue

            if match := operatorRegex.search(nestedString.string):
                #print (f'Found aka: {match.start()} - {match.end()}')
                newSub = nestedString.markSubStr(match.start() + len('operator'), match.end() - 1, Style.OPERATOR)
                rec(newSub)
                continue

            if (tn := nestedString.string.find('typename ')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('typename '), Style.INVISIBLE)
                continue

            if (tn := nestedString.string.find('template')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('template'), Style.TYPE)
                continue

            def findPairOf(startCh, endCh, styles={}):
                lessPos = -1
                for i, ch in enumerate(nestedString.string):
                    if ch == startCh:
                        if i < len(nestedString.string) - 1 and nestedString.string[i + 1] != endCh:
                            lessPos = i
                    if ch == endCh and lessPos > -1 and i > 0 and nestedString.string[i - 1] != startCh:
                        #breakpoint()
                        #print (f'{cm}Found {cs}<>{cm} pair.{ansi.all_off}')
                        newSub = nestedString.markSubStr(lessPos + 1, i, styles)
                        rec(newSub)
                        return True
                return False

            if findPairOf('<', '>'):
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
                            newSub = nestedString.markSubStr(0, i)
                            rec(newSub)
                            #print (f'{cm}Found {cs},{cm}.{ansi.all_off}')
                            return True
                        elif len(nestedString.string) > 1:
                            newSub = nestedString.markSubStr(i + 1, len(nestedString.string))
                            rec(newSub)
                            #print (f'{cm}Found ${cs},{cm}.{ansi.all_off}')
                            return True
                return False

            if findCommas():
                continue

            if (tn := nestedString.string.find('const ')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('const '), Style.DIM)
                continue

            if (tn := nestedString.string.find('class ')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('class '), Style.DIM)
                continue

            if (tn := nestedString.string.find('struct ')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('class '), Style.DIM)
                continue

            if (tn := nestedString.string.find('::type')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('::type'), Style.combineStyles(noisyStyle, Style.TYPE))
                continue

            if (tn := nestedString.string.find('::value')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('::value'), Style.combineStyles(noisyStyle, Style.TYPE))
                continue

            match = scopedTypeRegex.search(nestedString.string)
            if match and not nestedString.string.endswith('::'):
                scopeStr = match.group(1)
                typeStr = match.group(2)

                #if (typeStr == 'type' or typeStr == 'value') and len(scopeStr) >= 2:
                #    #breakpoint()
                #    newSub = nestedString.markSubStr(match.start() + len(scopeStr) - 2,
                #                                     match.start() + len(scopeStr) + len(typeStr),
                #                                     noisyStyle)
                #else:
                newSub = nestedString.markSubStr(match.start(), match.end(), Style.TYPE)
                newSub2 = newSub.markSubStr(0, len(scopeStr), scopeStyle)
                rec(newSub)
                rec(newSub2)
                #continue

            match = templateTypeRegex.search(nestedString.string)
            if match:
                newSub = nestedString.markSubStr(match.start(), match.end() - 2, Style.TYPE)
                rec(newSub)
                continue

            if (tn := nestedString.string.find('<>')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('<>'), [Style.TEMPLATEARGS, Style.OPERATOR])
                continue

            if (tn := nestedString.string.find('()')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('()'), [Style.PARAM, Style.OPERATOR])
                continue

            match = scopeLayerRegex.search(nestedString.string)
            if match and match.end() - match.start() < len(nestedString.string):
                newSub = nestedString.markSubStr(match.start(), match.end(), scopeStyle)
                rec(newSub)
                continue

            if nestedString.string.startswith('::') and len(nestedString.string) > 2:
                newSub = nestedString.markSubStr(0, 2)
                continue

            if nestedString.string.startswith(' ') and len(nestedString.string) > 1:
                newSub = nestedString.markSubStr(0, 1)
                continue

            if nestedString.string.endswith(' ') and len(nestedString.string) > 1:
                newSub = nestedString.markSubStr(len(nestedString.string) - 1, len(nestedString.string))
                continue

            if nestedString.string.startswith('_') and len(nestedString.string) > 1:
                newSub = nestedString.markSubStr(0, 1, noisyStyle)
                continue

            if nestedString.string.endswith('_') and len(nestedString.string) > 1:
                newSub = nestedString.markSubStr(len(nestedString.string) - 1, len(nestedString.string), noisyStyle)
                continue

            if (tn := nestedString.string.find('&&')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('&&'), Style.OPERATOR)
                continue

            if (tn := nestedString.string.find('&')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('&'), Style.OPERATOR)
                continue

            if (tn := nestedString.string.find('*')) >= 0:
                newSub = nestedString.markSubStr(tn, tn + len('*'), Style.OPERATOR)
                continue

    ns = ModdedString(message, [], Style.HIGHLIGHT if highlighted else {})
    rec(ns)
    return ns


class ModdedString:
    def __init__(self, strings, mods = [], styles = {}):
        cm = ansi.rgb_fg(192, 192, 192)
        cs = ansi.rgb_fg(192, 192, 92)
        #print (f'{cm}New ModdedString: string: {len(mods)} children - \'{cs}{"".join(strings)}\'')

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
            raise RuntimeError(f'"strings" must be a list of ModdedStrings or a ModdedString.')

        if len(self.strings) - len(self.mods) != 1:
            raise RuntimeError(f'There should be one more string than mod.')

        self.styles = Style.normalizeStyles(styles)


    def reprRec(self, depth = 0):
        cm = ansi.rgb_fg(192, 192, 192)
        cs = ansi.rgb_fg(255, 157, 184)
        src = ''
        src += f'{cm}{"- " * depth}children: {cs}{len(self.mods)}\n'
        src += f'{cm}{"- " * depth}styles: {cs}{"|".join([s.name for s in self.styles])}\n'
        src += ''.join([f'{cm}{"- " * depth}\'{cs}{s}{cm}\'\n' for s in self.strings])
        src += f'{ansi.all_off}\n'
        for n in self.mods:
            src += n.reprRec(depth + 1)

        return src


    def __repr__(self):
        return self.reprRec()


    def displaceSubStr(self, start, end, forgetIt=True, styles={}):
        cm = ansi.rgb_fg(63, 63, 255)
        cs = ansi.rgb_fg(127, 255, 127)

        styles = Style.normalizeStyles(styles)

        #print (f'{cm}DisplaceSubStr: start: {start}; end: {end}; from: \'{cs}{self.string[0:start]}{cm}{self.string[start:end]}{cs}{self.string[end:]}{cm}\' as {"|".join([s.name for s in styles.keys()])}{ansi.all_off}')
        #print (f'{cm}     Top self is:\n{ansi.all_off}{self}')

        #if self.string[start:end] == 'enable':
        #    breakpoint()

        removals = []
        newStrings = []
        newMods = []
        totalLen = 0
        strStart = -1
        strEnd = -1
        newStrL = None
        newStrR = None
        #breakpoint()
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

        #print (f'newStrL: {newStrL}')
        #print (f'newStrR: {newStrR}')

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

        #print (f'{cm}Displaced string: strStart: {strStart}; strEnd: {strEnd} \'{cs}{m.string}\'')
        #print (f'{cm}     Now self is:\n{ansi.all_off}{self}')

        assert(len(self.strings) - len(self.mods) == 1)

        return m


    @property
    def string(self):
        return ''.join(self.strings)


    def markSubStr(self, start, end, styles={}):
        assert(start >= 0 and start < len(self.string))
        assert(end > 0 and end <= len(self.string) and start < end)
        return self.displaceSubStr(start, end, False, styles)


    def render(self, styles={}):
        src = ''

        styles = Style.normalizeStyles(styles)

        styles.pop(Style.SCOPE, None)
        styles.pop(Style.NOISY, None)
        styles.pop(Style.OPERATOR, None)
        #styles.pop(Style.TYPE, None)

        cascadedStyles = Style.combineStyles(self.styles, styles)
        fg, bg = Style.getColors(cascadedStyles)

        if Style.INVISIBLE not in cascadedStyles:
            for s, m in zip(self.strings, self.mods):
                if len(s) > 0:
                    src += f'{fg}{bg}{s}'
                src += m.render(cascadedStyles)
            src += f'{fg}{bg}{self.strings[-1]}'

        return src


    '''
candidate: ‘
template<class _Ostream, class _Tp>
typename std::enable_if<
    std::__and_<
        std::__not_<
            std::is_lvalue_reference<
                _Tp
            >
        >,
        std::__is_convertible_to_basic_ostream<
            _Ostream
        >,
        std::__is_insertable<
            typename std::__is_convertible_to_basic_ostream<
                _Tp
            >::__ostream_type,
            const _Tp&,
            void
        >
    >::value,
    typename std::__is_convertible_to_basic_ostream<
        _Tp
    >::__ostream_type
>::type std::operator<<(_Ostream&&, const _Tp&)’
'''


    '''
0         1         2         3         4         5         6         7         8         9         0
0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789
template<> typename std::enable_if<>::type std::operator(_Ostream&&, const _Tp&)
,
 typename std::__is_convertible_to_basic_ostream<>::__ostream_type
,
'''



class NestedString:
    def __init__(self, string, start = 0, end = 0, styles = {}):
        print (f'{ansi.rgb_fg(192, 192, 192)}New NestedString: start: {start}; end: {end}; string: \'{ansi.rgb_fg(192, 192, 92)}{string}\'')
        self.string = string
        self.start = start
        self.end = end if end > 0 else len(string)
        self.nested = []
        if isinstance(styles, dict):
            self.styles = styles
        elif isinstance(styles, list):
            self.styles = {s:None for s in styles}
        elif isinstance(styles, Style):
            self.styles = {styles: None}


    def reprRec(self, depth = 0):
        src = f'{" " * depth * 2}{ansi.rgb_fg(192, 192, 192)}start: {self.start}, end: {self.end}, {len(self.nested)} children - \'{ansi.rgb_fg(255, 157, 184)}{self.string}{ansi.all_off}\'\n'
        for n in self.nested:
            src += n.reprRec(depth + 1)

        return src


    def __repr__(self):
        return self.reprRec()


    def displaceSubStr(self, start, end, forgetIt=True, styles={}):
        cm = ansi.rgb_fg(63, 63, 255)
        cs = ansi.rgb_fg(127, 255, 127)
        print (f'{cm}DisplaceSubStr: start: {start}; end: {end}; from: \'{cs}{self.string[0:start]}{cm}{self.string[start:end]}{cs}{self.string[end:]}{cm}\'{ansi.all_off}')
        removals = []
        for i, nns in enumerate(self.nested):
            if nns.start >= end:
                #nns.start -= (end - start)
                #nns.end -= (end - start)
                pass
            elif nns.start >= start:
                #nns.start -= start
                #nns.end -= start
                removals.append(i)
            elif nns.end < start:
                pass

        newSub = NestedString(self.string[start : end], start, end, styles)
        newSub.nested = [self.nested[i] for i in removals]

        removals.sort(reverse=True)
        for i in removals:
            del self.nested[i]

        self.string = self.string[:start] + self.string[end:]

        if not forgetIt:
            # add the new nested string at the correct place
            for i, nns in enumerate(self.nested):
                if nns.start > start:
                    #self.nested.insert(i - 1, newSub)
                    self.nested.append(newSub)
                    print (f'{ansi.rgb_fg(63, 63, 255)}Displaced string: \'{ansi.rgb_fg(0, 255, 255)}{newSub.string}{ansi.rgb_fg(63, 63, 255)}\'')
                    print (f'{ansi.rgb_fg(63, 63, 255)}     Now self is:\n{ansi.all_off}{self}')
                    return newSub

            # we didn't add it before anything, so add it after all
            self.nested.append(newSub)
            print (f'{ansi.rgb_fg(63, 63, 255)}Displaced string: \'{ansi.rgb_fg(0, 255, 255)}{newSub.string}{ansi.rgb_fg(63, 63, 255)}\'')
            print (f'{ansi.rgb_fg(63, 63, 255)}     Now self is:\n{ansi.all_off}{self}')
            return newSub

        print (f'{ansi.rgb_fg(63, 63, 255)}Displaced string: \'{ansi.rgb_fg(0, 255, 255)}{newSub.string}{ansi.rgb_fg(63, 63, 255)}\'')
        print (f'{ansi.rgb_fg(63, 63, 255)}     Now self is:\n{ansi.all_off}{self}')

        return newSub


    def markSubStr(self, start, end, styles={}):
        #breakpoint()
        assert(start >= 0 and start < len(self.string))
        assert(end > 0 and end <= len(self.string) and start < end)
        return self.displaceSubStr(start, end, False, styles)


    def removeSubStr(self, start, end):
        assert(start >= 0 and start < len(self.string))
        assert(end > 0 and end <= len(self.string) and start < end)
        return self.displaceSubStr(start, end)


    def render(self, styles={}):
        #breakpoint()
        src = self.string
        bareSrc = self.string
        ps = 0

        cascadedStyles = {**self.styles, **styles}
        fg, bg = Style.getColors(cascadedStyles)

        #nested = sorted(self.nested, key=lambda x: x.start)
        print ('--- render')
        if len(self.nested) > 0:
            nested = reversed(self.nested)
            for i, nns in enumerate(nested):
                sc = ''
                if nns.start > 0:
                    sc = f'{fg}{bg}'
                ec = ''
                if nns.start < len(self.string) - 1:
                    ec = f'{fg}{bg}'

                inner = nns.render(cascadedStyles)
                #src = f'{sc}{self.string[0:nns.start]}{inner}{ec}{self.string[nns.start:]}'
                bareSrc = f'{bareSrc[0:nns.start]}{inner}{bareSrc[nns.start:]}'

                print (bareSrc)
        else:
            bareSrc = f'{self.string}'
            print (bareSrc)

            #if nns.start - ps > 0:
            #    fg, bg = Style.getColors(cascadedStyles)
            #    src += f'{fg}{bg}'
            #    src += self.string[ps:nns.start]
            #ps = nns.start
            #src += nns.render(cascadedStyles)

        #if len(self.string) - ps > 0:
        #    fg, bg = Style.getColors(cascadedStyles)
        #    src += f'{fg}{bg}'
        #    src += self.string[ps:]

        return bareSrc


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
        if isinstance(styles, list):
            styles = {s: None for s in styles}
        elif isinstance(styles, Style):
            styles = {styles: None}
        if len(styles) > 0:
            self.subStrs = [SubStr(0, len(initStr), styles)]
        else:
            self.subStrs = [SubStr(0, len(initStr), {})]

    def markSubStr(self, start, end, styles):
        assert(start <= end)
        assert(start >= 0)
        assert(end <= len(self.string))

        if isinstance(styles, list):
            styles = {s: None for s in styles}
        elif isinstance(styles, Style):
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

        src = ''
        cur = 0
        subStrCur = 0

        subStrStack = [subStrs[0]]
        styleStack = [subStrs[0].styles]

        while len(subStrStack) > 0:
            sub = subStrStack[-1]
            lenToThisEnd = sub.end - cur
            lenToNextStart = lenToThisEnd + 1
            if len(subStrs) > subStrCur + 1:
                lenToNextStart = subStrs[subStrCur + 1].start - cur
            amt = min(lenToThisEnd, lenToNextStart)

            if amt > 0:
                fg, bg = Style.getColors(styleStack[-1])
                if Style.INVISIBLE not in styleStack[-1]:
                    src += f'{fg}{bg}'
                    src += self.string[cur : cur + amt]
                cur += amt

            # if we're closing a style before we open the next one,
            if lenToThisEnd < lenToNextStart:
                subStrStack.pop()
                styleStack.pop()
            else:
                subStrCur += 1
                subStrStack.append(subStrs[subStrCur])
                styles = {**styleStack[-1], **subStrs[subStrCur].styles}
                styleStack.append(styles)

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

        bgColor = f'{ansi.rgb_bg(0, 31, 0) if topIssueCounter.count % 2 == 1 else ansi.rgb_bg(0, 0, 31)}'

        if len(self.notes) + len(self.children) > 0:
            issueCounter.inc()
            src += f'{bgColor}{issueCounter.count:}: {"-" if self.issueOpened else "+"}{ansi.all_off} '
        else:
            src += f'{bgColor}    {ansi.all_off} '

        if self.kind == 'error':
            src += f'{ansi.rgb_fg(255, 0, 0)} Err: '
        elif self.kind == 'warning':
            src += f'{ansi.rgb_fg(255, 255, 0)}Warn: '
        if self.kind == 'note':
            src += f'{ansi.rgb_fg(0, 255, 255)}Note: '

        pathCounter.inc()
        if self.pathOpened:
            src += f'{ansi.rgb_fg(255, 255, 255)}'
        else:
            src += f'{ansi.rgb_fg(127, 127, 127)}'
        src += f'{" " if depth > 0 else ""}p{pathCounter.count}:{" " if depth == 0 else ""} '
        src += f'{strPath(self.path, self.pathOpened)}'
        src += f' {ansi.rgb_fg(0, 127, 127)}({self.line}): '

        if self.messageOpened:
            src += f'{ansi.rgb_fg(255, 255, 255)}'
        else:
            src += f'{ansi.rgb_fg(127, 127, 127)}'
        src += f'm{pathCounter.count}: '

        msg = sanitizeString(self.message, self.messageOpened, depth == 0 and self.issueOpened)
        msg = justifyMessage(msg.render(), len(strNoColor(src)), termWidth, bgColor)
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
        return self.strSelf(0)


def printDivision():
    termWidth, _ = shutil.get_terminal_size((80, 20))
    for i in range(0, termWidth):
        y = int(math.sin(2 * math.pi  * i / termWidth * 3) * 255.0)
        if y < 0:
            print (ansi.rgb_fg(0, 0, -y), end='')
        else:
            print (ansi.rgb_fg(0, y, 0), end='')
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
    fsrc = f'[{",".join([f"{s}" for s in src.strip().split(endl)])}]'

    try:
        issuesSrc = json.loads(fsrc)
    except:
        print(src)
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
            print (iss.strSelf(ec, pc, tc), end='')

        command = ''
        while True:
            command = input(f'{ansi.all_off}Command? ').strip()

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
                print (f'''{ansi.rgb_fg(192, 0, 0)}Type an integer to open/close an issue,
     "*" to open/close all issues,
     "p" and an integer to expand/contract a path, or "*" to expand/contract all paths,
     "m" and an integer to expand/contract a message, or "*" to expand/contract all messages,
  or "q" to quit.{ansi.all_off}''')
