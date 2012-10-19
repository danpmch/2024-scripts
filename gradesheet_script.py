
import os
import sys
import zipfile
import xml.dom.minidom
import traceback

def get_contents( odt ):
  files = odt.infolist()
  for file in files :
    if file.orig_filename == "content.xml" :
      file_str = odt.read( file )
      return file_str

def para_to_str( para ):
  if para.childNodes != []:
    para_str = para.childNodes[ 0 ].data
  else:
    para_str = ""

  return para_str

def node_to_text( node ):
  text = ""
  for child in node.childNodes:
    if child.nodeType == child.TEXT_NODE:
      text += str( child.data )
    text += node_to_text( child )
  return text

def row_to_strs( row ):
  cells = row.getElementsByTagName( "table:table-cell" )
  strs = map( node_to_text, cells )
  return strs

class GradingElement:
  def __init__( self, doc, row ):
    self.doc = doc

    strs = row_to_strs( row )
    self.max_grade = int( strs[ 1 ] )
    self.grading_str = strs[ 0 ] + ' (' + str( self.max_grade ) + '): '
    self.grade_element = row.getElementsByTagName( 'table:table-cell' )[ 2 ].getElementsByTagName( 'text:p' )[ 0 ]
    self.grade = 0

  def grading_str( self ):
    return self.grading_str

  def get_grade( self ):
    return self.grade

  def get_max_grade( self ):
    return self.max_grade

  def set_grade( self, val ):
    # clamp grade to range [ 0, max_grade ]
    self.grade = min( self.max_grade, int( val ) )
    self.grade = max( 0, int( val ) )

  def finalize_grade( self ):
    text_node = self.doc.createTextNode( str( self.grade ) )
    self.grade_element.appendChild( text_node )

grading_comment_dictionary = {
    "no_header":
'''
You need to include a header comment in each source file you submit with the name/netid of each author, and a brief description of what the source
code is supposed to do. At least indicate where the assignment description can be found in the textbook.
''',

    "no_comments":
'''
Your source code needs to have more comments. Make sure to at least have comments describing the intended behavior of critical functions, particularly in base classes.
''',

    "bad_include":
'''
Your code didn't compile at first because at least one of the file names in your include statements didn't exactly match the real file
name. Remember to put a CAPITAL H on the end of all your header files, because the submitted file will have an H on the end and on Linux
(the OS I grade with) capitalization matters.
''',

    "no_include":
'''
Your code didn't compile at first because you forgot to include a header in at least one of your files.
''',

    "no_srand":
'''
You didn't seed the random number generator with a call to srand() before making calls to rand(). This means that your random
numbers actually follow a very predictable pattern, your calls to rand() always return the same sequence of numbers.
''',

    "constructor_duplicated":
'''
While your derived constructors do pass the appropriate member variables to the parent constructor, they also manually set the same values in their constructor. This defeats the purpose of passing the value to the parent, the derived constructor shouldn't touch the values beyond passing them to the parent.
'''
}

class GradingSheet:
  def __init__( self, filename ):
    self.orig_odt = zipfile.ZipFile( filename )
    contents = get_contents( self.orig_odt )
    self.doc = xml.dom.minidom.parseString( contents )

    tables = self.doc.getElementsByTagName( "table:table" )
    rows = tables[ 0 ].getElementsByTagName( "table:table-row" )

    self.grades = []
    for row in rows[1:-1]:
      grade = GradingElement( self.doc, row )
      self.grades.append( grade )

    self.total_grade = GradingElement( self.doc, rows[ -1 ] )

    self.comments = []
    self.text_body = self.doc.getElementsByTagName( "office:text" )[ -1 ]

  def read_score( self, grade ):
    done = False
    while not done:
      try:
        score = self.get_score( grade )
        done = True
        return score
      except KeyboardInterrupt:
        raise
      except Exception:
        print traceback.format_exc()
        print "Error encountered, trying again."


  def get_score( self, grade ):
      new_str = raw_input( grade.grading_str )
      if new_str is '':
        # assign max grade by default
        new_grade = grade.get_max_grade()
      elif new_str[ 0 ] is '%':
        # evaluate input as mathematical expression returning int
        scope = { '__builtins__':globals()[ '__builtins__' ], 'max': grade.get_max_grade() }
        new_grade = int( eval( new_str[ 1: ], scope ) )
        print "Evaluated score: %d" % new_grade
      else:
        # evaluate input as integer
        new_grade = int( new_str )

        # score negative numbers relative to max grade
        if new_grade < 0:
          new_grade += grade.get_max_grade()
          print "Evaluated score: %d" % new_grade

      return new_grade

  def read_comment( self ):
    done = False
    while not done:
      try:
        comment = self.get_comment()
        done = True
      except KeyboardInterrupt:
        raise
      except Exception:
        print traceback.format_exc()
        print "Error encountered, trying again."

  def get_comment( self ):
      new_comment = raw_input( "Explain reason for lost points: " )
      words = new_comment.split( ' ' )
      keywords = filter( lambda s: s[ 0 ] is '%' and s is not '%',  words )
      regular_words = filter( lambda s: s[ 0 ] is not '%' or s is '%', words )
      stock_comments = [ grading_comment_dictionary[ keyword[1:] ] for keyword in keywords ]
      self.comments.extend( stock_comments )
      self.comments.append( ' '.join( regular_words ) )

  def grade_all( self ):
    self.comments = []
    self.total_grade.set_grade( 0 )
    for grade in self.grades:
      score = self.read_score( grade )
      grade.set_grade( score )
      self.total_grade.set_grade( self.total_grade.get_grade() + grade.get_grade() )

      if score < grade.get_max_grade():
        self.read_comment()

  def create_paragraph( self, text ):
    node = self.doc.createElement( "text:p" )
    text_node = self.doc.createTextNode( text )
    node.appendChild( text_node )
    return node

  def write_new_grades( self, path ):
    for grade in self.grades:
      grade.finalize_grade()

    self.total_grade.finalize_grade()

    if len( self.comments ) == 0:
      self.comments.append( "Nice job." )

    # write all comments to bottom of file, after "COMMENTS:" line
    for comment in self.comments:
      self.text_body.appendChild( self.create_paragraph( "" ) )
      self.text_body.appendChild( self.create_paragraph( comment ) )

    doc_str = self.doc.toxml( 'utf-8' )

    with zipfile.ZipFile( path + 'grade_' + str( self.total_grade.get_grade() ) + '.odt', 'w' ) as new_file:
      files = self.orig_odt.infolist()
      for f in files:
        if f.filename != 'content.xml':
          new_file.writestr( f, self.orig_odt.read( f ) )
        else:
          new_file.writestr( f, doc_str )

if len( sys.argv ) < 3:
  print "Usage: script template_sheet_path output_directory"
else:
  grading_sheet = GradingSheet( sys.argv[ 1 ] )
  done = False
  while not done:
    try:
      grading_sheet.grade_all()
      grading_sheet.write_new_grades( sys.argv[ 2 ] )
      done = True
    except KeyboardInterrupt:
      raise
    except Exception:
      print traceback.format_exc()
      print "Error encountered, trying again."



