#!/usr/bin/python -tt
# Copyright 2010 Google Inc.
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

# Google's Python Class
# http://code.google.com/edu/languages/google-python-class/


import sys

def utilFunc(filename):
    wordCountDict = {}
    f = open(filename, 'rU')
    for line in f:
        listOfWords = line.split()
        for word in listOfWords:
            word = word.lower()
            if word in wordCount:
                wordCountDict[word] += 1
            else:
                wordCountDict[word] = 1
    f.close()
    return wordCountDict


def count(countTuple):
    return countTuple[1]


def print_words(filename):
    wordCount = utilFunc(filename)
    
    wordsList = sorted(wordCount.keys())
    for word in wordsList:
        print (word, wordCount[word])
    

def print_top(filename):
    wordCount = utilFunc(filename)
    
    wordsList = sorted(wordCount.items(), key=count, reverse=True)
    topTwentyList = wordsList[:20]
    for word in topTwentyList:
        print (word[0], word[1])


def main():
  if len(sys.argv) != 3:
    print 'usage: ./wordcount.py {--count | --topcount} file'
    sys.exit(1)

  option = sys.argv[1]
  filename = sys.argv[2]
  if option == '--count':
    print_words(filename)
  elif option == '--topcount':
    print_top(filename)
  else:
    print 'unknown option: ' + option
    sys.exit(1)

if __name__ == '__main__':
  main()
