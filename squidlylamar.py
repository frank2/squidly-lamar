#!/usr/bin/env python

import os
import sys

class KeywordToken:
   pass

class ValueToken:
   pass

class PatternToken:
   pass

class HostDeclaration:
   pass

class StateMachine:
   def __init__(self, tape, init_state):
      self.tape = tape
      self.current_state = init_state

   def run(self):
      read = 0

      while read < len(self.tape):
         #print '[DEBUG] Entering state %s at tape index %d' % (repr(self.current_state), read)
         read = self.current_state(read)

class StateError(Exception):
   pass

class SSHConfigMachine(StateMachine):
   ALL_WHITESPACE = set(' \t\r\n')
   LINE_WHITESPACE = set(' \t,')
   ENTRY_WHITESPACE = set('\r\n')

   def __init__(self, filename):
      fp = open(filename, 'r')
      data = fp.read()
      fp.close()

      self.current_host = "*"
      self.current_keyword = None
      self.current_argument = None
      self.current_arguments = None
      self.current_line = 1

      self.configuration = dict()

      StateMachine.__init__(self, data, self.init_state)

   def comment(self, tape_index):
      c = self.tape[tape_index]

      if not c in self.ENTRY_WHITESPACE:
         return tape_index+1
      else:
         self.current_state = self.entry_whitespace

      return tape_index

   def entry_whitespace(self, tape_index):
      c = self.tape[tape_index]

      if not self.current_keyword is None and self.current_argument is None and self.current_arguments is None:
         raise StateError("unexpected end-of-line parsing %s for %s. (line %d)" % (self.current_keyword, self.current_host, self.current_line))
      if c in self.ALL_WHITESPACE and self.current_keyword is None:
         self.current_state = self.init_state
         return tape_index

      if self.current_argument:
         self.current_argument = ''.join(self.current_argument)

         if self.current_arguments is None:
            self.current_arguments = [self.current_argument]
         else:
            self.current_arguments.append(self.current_argument)

      self.store_keyword()
      self.current_state = self.init_state

      if self.current_keyword == 'Host':
         self.current_host = ', '.join(self.current_arguments)

      self.current_keyword = None
      self.current_argument = None
      self.current_arguments = None
      self.current_line += 1

      return tape_index+1

   def line_whitespace(self, tape_index):
      c = self.tape[tape_index]

      if c in self.LINE_WHITESPACE:
         return tape_index+1
      elif c == '#':
         self.current_state = self.comment
      elif c in self.ENTRY_WHITESPACE:
         self.current_state = self.entry_whitespace
      else:
         self.current_state = self.argument

      return tape_index

   def keyword(self, tape_index):
      c = self.tape[tape_index]

      if c in self.ENTRY_WHITESPACE:
         raise StateError("unexpected end-of-line attempting to parse keyword for %s. (line %d)" % (self.current_host, self.current_line))
      elif c in self.LINE_WHITESPACE:
         if self.current_keyword is None:
            raise StateError("found argument whitespace but have no keyword for %s. (line %d)" % (self.current_host, self.current_line))

         self.current_keyword = ''.join(self.current_keyword)
         self.current_state = self.line_whitespace
         return tape_index

      if self.current_keyword is None:
         self.current_keyword = list()
      else:
         self.current_keyword.append(c)

      return tape_index+1

   def store_keyword(self):
      print self.current_host, self.current_keyword, self.current_arguments
      #print "[%s] %s: %s" % (self.current_host, self.current_keyword, ', '.join(self.current_arguments))

   def argument(self, tape_index):
      c = self.tape[tape_index]

      if c in self.ENTRY_WHITESPACE:
         self.current_state = self.entry_whitespace
      elif c in self.LINE_WHITESPACE:
         if not self.current_argument is None:
            self.current_argument = ''.join(self.current_argument)

            if self.current_arguments is None:
               self.current_arguments = list()

            self.current_arguments.append(self.current_argument)
            self.current_argument = None

         self.current_state = self.line_whitespace
      else:
         if self.current_argument is None:
            self.current_argument = list()

         self.current_argument.append(c)
         return tape_index+1

      return tape_index

   def enclosed_argument(self, tape_index):
      pass

   def init_state(self, tape_index):
      c = self.tape[tape_index]

      if c == '\n':
         self.current_line += 1

      if c in self.ALL_WHITESPACE:
         return tape_index+1
      elif c == '#':
         self.current_state = self.comment
      else:
         self.current_keyword = list()
         self.current_state = self.keyword

      return tape_index

# states:
#     init
#     comment
#     keyword token
#     argument token
#     pattern token
#     host declaration

if __name__ == '__main__':
   ssh_machine = SSHConfigMachine("/home/purple/.ssh/config.harvest")
   ssh_machine.run()
