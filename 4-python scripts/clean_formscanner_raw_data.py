#! /Users/peej/anaconda/envs/grading

"""This file is used to grade exam data recorded to bubblesheet and graded
by the formscanner app.
"""
import sys

# this changes the working directory so we can import `grader_functions`
sys.path.insert(0, './functions/')

# sys.path.insert(0, '/Users/peej13/Library/Mobile Documents/'
#                    'com~apple~CloudDocs/'
#                    'Lone Star College Classes/Lone Star Stuff/'
#                    '~scan and grade exams/4-python scripts/functions/')

from grader_functions import *

# course roster dictionary
rosters = {'1401_6303': 'PHYS-1401 6303 roster.csv',
           '1410_6301': 'PHYS-1410 6301 roster.csv'}

course_number, roster_file_name = list_picker(rosters)

# get the path from the course number
roster_file_path = 'data/' + roster_file_name

# get the formscanner data name
exam_number = input('What exam number is this? ')

if exam_number == 'final exam':
    file_name = course_number + ' FA18 ' + exam_number + \
                ' scanned bubblesheets.csv'
else:
    file_name = course_number + ' FA18 exam ' + exam_number + \
                ' scanned bubblesheets.csv'

formscanner_data_path = 'data/' + file_name

# path to the save file
save_path = 'results/' + file_name[-24:-4] + ' formatted.csv'

# create a student data object
# number_of_questions = input('How many questions total? ')
# # class_data = ClassData(int(number_of_questions))
class_data = ClassData()

# ingest that sweet sweet ID data
class_data.ingest_roster(roster_file_path)

# ingest that delicious formscanner data
class_data.ingest_formscanner_data(formscanner_data_path)

# clean up the formscanner data
class_data.clean_formscanner_data()

# match name with student ID number
class_data.match_roster_to_responses()

# match name with student ID number again to see if corrections took
class_data.match_roster_to_responses()

# save data to CSV file
class_data.write_to_csv(save_path)

print(class_data)
# print(class_data.id_to_name)
print('\nthe question fieldnames are:')
print(class_data.ques_fieldnames)
print('\nthe ID fieldnames are:')
print(class_data.id_fieldnames)
print('\nthe FORM fieldname is:')
print(class_data.form_fieldname)
