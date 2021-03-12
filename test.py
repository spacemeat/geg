from geg import geg

s = geg.HierString('-foo-bar-baz-')
#print (s.render())

s.markSubStr(9, 12, geg.Style.HIGHLIGHT)
#print (str(s))
s.markSubStr(5, 8, [geg.Style.PATH, geg.Style.DIR])
#print (str(s))
s.markSubStr(1, 4, geg.Style.PATH)
#print (str(s))
print (s.render())
