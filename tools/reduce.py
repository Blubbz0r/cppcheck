
import subprocess
import os
import sys

CMD = None
EXPECTED = None
SEGFAULT = False
FILE = None
BACKUPFILE = None
for arg in sys.argv[1:]:
  if arg.startswith('--cmd='):
    CMD = arg[arg.find('=')+1:]
  elif arg.startswith('--expected='):
    EXPECTED = arg[arg.find('=')+1:]
  elif arg.startswith('--file='):
    FILE = arg[arg.find('=')+1:]
    BACKUPFILE = FILE + '.bak'
  elif arg == '--segfault':
    SEGFAULT = True

if CMD is None:
  print('Abort: No --cmd')
  sys.exit(1)

if SEGFAULT == False and EXPECTED is None:
  print('Abort: No --expected')
  sys.exit(1)

if FILE is None:
  print('Abort: No --file')
  sys.exit(1)

print('CMD='+CMD)
if SEGFAULT:
  print('EXPECTED=SEGFAULT')
else:
  print('EXPECTED='+EXPECTED)
print('FILE='+FILE)

def runtool():
  p = subprocess.Popen(CMD.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  comm = p.communicate()
  if SEGFAULT:
    if p.returncode != 0:
      return True
  elif p.returncode == 0:
    out = comm[0] + '\n' + comm[1]
    if (out.find('error:') < 0) and (out.find(EXPECTED) > 0):
      return True
  return False

def writefile(filename, filedata):
  f = open(filename, 'wt')
  for line in filedata:
    f.write(line)
  f.close()

def replaceandrun(what, filedata, i, line):
  print(what + ' ' + str(i+1) + '/' + str(len(filedata)) + '..')
  bak = filedata[i]
  filedata[i] = line
  writefile(FILE, filedata)
  if runtool() == True:
    print('pass')
    writefile(BACKUPFILE, filedata)
    return True
  print('fail')
  filedata[i] = bak
  return False

def replaceandrun2(what, filedata, i, line1, line2):
  print(what + ' ' + str(i+1) + '/' + str(len(filedata)) + '..')
  bak1 = filedata[i]
  bak2 = filedata[i+1]
  filedata[i] = line1
  filedata[i+1] = line2
  writefile(FILE, filedata)
  if runtool() == True:
    print('pass')
    writefile(BACKUPFILE, filedata)
  else:
    print('fail')
    filedata[i] = bak1
    filedata[i+1] = bak2

def removecomments(filedata):
  for i in range(len(filedata)):
    line = filedata[i]
    if line.find('//') >= 0:
      replaceandrun('remove comment', filedata, i, line[:line.find('//')].rstrip())

def checkpar(line):
  par = 0
  for c in line:
    if c=='(' or c=='[':
      par = par + 1
    elif c==')' or c==']':
      par = par - 1
      if par<0:
        return False
  return par == 0

def combinelines(filedata):
  if len(filedata) < 3:
    return

  lines = []

  for i in range(len(filedata)-1):
    fd1 = filedata[i].rstrip()
    if fd1.endswith(','):
      fd2 = filedata[i+1].lstrip()
      if fd2 != '':
        lines.append(i)

  chunksize = len(lines)
  while chunksize > 10:
    i = 0
    while i < len(lines):
      i1 = i
      i2 = i + chunksize
      i = i2
      if i2 > len(lines):
        i2 = len(lines)

      filedata2 = list(filedata)
      for line in lines[i1:i2]:
        filedata2[line] = filedata2[line].rstrip() + filedata2[line+1].lstrip()
        filedata2[line+1] = ''

      if replaceandrun('combine lines', filedata2, lines[i1]+1, ''):
        filedata = filedata2
        lines[i1:i2] = []
        i = i1

    chunksize = chunksize / 2

  for line in lines:
    fd1 = filedata[line].rstrip()
    fd2 = filedata[line+1].lstrip()
    replaceandrun2('combine lines', filedata, line, fd1+fd2, '')

def removeline(filedata):
  stmt = True
  for i in range(len(filedata)):
    line = filedata[i]
    strippedline = line.strip()

    if len(strippedline) == 0:
      continue

    if stmt and strippedline[-1]==';' and checkpar(line) and line.find('{')<0 and line.find('}')<0:
      replaceandrun('remove line', filedata, i, '')

    elif stmt and strippedline.find('{') > 0 and strippedline.find('}') == len(strippedline) - 1:
      replaceandrun('remove line', filedata, i, '')

    if ';{}'.find(strippedline[-1]) >= 0:
      stmt = True
    else:
      stmt = False


def removeincludes(filedata):
  for i in range(len(filedata)):
    if filedata[i].startswith('#include '):
      replaceandrun('remove #include', filedata, i, '')

def removeemptyblocks(filedata):
  if len(filedata) < 3:
    return

  i = 0
  while i < len(filedata):
    if filedata[i].strip() == '':
      filedata.pop(i)
    else:
      i = i + 1

  for i in range(len(filedata)-1):
    fd1 = filedata[i].rstrip()
    fd2 = filedata[i+1].strip()
    if checkpar(fd1) and fd1.endswith('{') and fd2 == '}':
      replaceandrun2('remove block', filedata, i, '', '')

def removenamespaces(filedata):
  if len(filedata) < 3:
    return filedata

  stmt = True

  for i in range(len(filedata)):
    line = filedata[i]
    strippedline = line.strip()

    if len(strippedline) == 0:
      continue

    stmt1 = stmt
    if ';{}'.find(strippedline[-1]) >= 0:
      stmt = True
    else:
      stmt = False

    if stmt1 == False:
      continue

    if strippedline.find('}') < 0 and strippedline.find('{') == len(strippedline)-1:
      i2 = i + 1
      level = 1
      while i2 < len(filedata) and level > 0:
        #print(str(i2)+':'+str(level)+':'+filedata[i2])
        for c in filedata[i2]:
          if c == '}':
            level = level - 1
            if level <= 0:
              break
          elif c == '{':
            level = level + 1
        i2 = i2 + 1
      if level == 0 and (filedata[i2-1].strip().endswith('}') or filedata[i2-1].strip().endswith('};')):
        #print(str(i)+';'+str(i2))
        filedata2 = list(filedata)
        ii = i
        while ii < i2:
          filedata2[ii] = ''
          ii = ii + 1
        if replaceandrun('remove codeblock', filedata2, i, ''):
          filedata = filedata2
  return filedata

# reduce..
print('Make sure error can be reproduced...')
if runtool() == False:
     print("Cannot reproduce")
     sys.exit(1)

f = open(FILE, 'rt')
filedata = f.readlines()
f.close()

writefile(BACKUPFILE, filedata)

print('remove comments...')
removecomments(filedata)
print('combine lines..')
combinelines(filedata)
print('remove namespaces...')
filedata = removenamespaces(filedata)
print('remove includes...')
removeincludes(filedata)
print('remove line...')
removeline(filedata)
print('remove includes...')
removeincludes(filedata)
print('remove empty blocks...')
removeemptyblocks(filedata)
print('remove namespaces...')
filedata = removenamespaces(filedata)



writefile(FILE, filedata)
