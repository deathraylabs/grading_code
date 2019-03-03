""" Script to test modifications to bubblesheet grader

FormScanner question groups must use the following names:
response     => group name for question responses
OrgDefinedId => group name for student ID number
form         => group name for form letter
"""

import pandas as pd
import numpy as np
import sys
# module for easy directory manipulation
import os

# in this case `insert` is a property of lists
# this code allows us to import the functions file
# this changes the working directory so we can import `grader_functions`
sys.path.insert(0, './functions/')

from grader_functions import *


# --------------- data used for testing --------------- #

# course roster dictionary
rosters = {'1401_6303': 'PHYS-1401 6303 roster.csv',
           '1410_6301': 'PHYS-1410 6301 roster.csv'}

course_number, roster_file_name = list_picker(rosters)

# get the path from the course number
# assuming that data directory is above current working directory
roster_file_path = 'data/' + roster_file_name

exam_data_path = os.path.join('..', 'results/',
                              'scanned bubblesheets formatted.csv')

# create class data instance
class_data = ClassData()

# todo: get rid of this temporary question number code
class_data.number_of_questions = 30

# get those questions
number_of_questions = class_data.get_num_of_ques()

# get the roster using pandas instead of my home-built function
roster_array = pd.read_csv(roster_file_path)

# get the formatted exam data using pandas
exam_data = pd.read_csv(exam_data_path)

# convert to numpy array for manipulation ease
exam_data_array = exam_data.to_numpy()

# create a new array that just includes response data
m_responses = exam_data_array[:, 3:]

# second to last line happens to be keyA and next is keyB
# this is only true for data cleaned with formscanner reformatter
exam_keyA = m_responses[-2]
exam_keyB = m_responses[-1]

# might as well just score each test against both keys
exam_keys = (exam_keyA, exam_keyB)

# --------------- actual grader code -------------------

# list to contain scored arrays
scored_arrays = []

# check each item against the key for both keys
# drop the two last rows that contain the answer keys
for key in exam_keys:
    scored = key == m_responses[:-2]
    scored_arrays.append(scored)

# total number of test takers (using first scored array)
# num_test_takers = m_scored.shape[0]
num_test_takers = scored_arrays[0].shape[0]
print('{} examinees total.\n'.format(num_test_takers))

# number of test items (questions)
num_questions = scored_arrays[0].shape[1]
print('{} questions total\n'.format(num_questions))

num_correct_arrays = []

# number of items each student gets correct, in array format
for scored in scored_arrays:
    num_correct_array = scored.sum(axis=1, keepdims=True)
    num_correct_arrays.append(num_correct_array)

# array containing number of correct answers graded against each key
correct_for_keyA_and_keyB = np.hstack((num_correct_arrays[0],
                                       num_correct_arrays[1]))
print('Array of number correct for each key:\n'
      '{}\n'.format(correct_for_keyA_and_keyB))

# grab the largest number of correct items between keys
max_number_correct = correct_for_keyA_and_keyB.max(axis=1)
print('Array of max number of correct answers:\n'
      '{}\n'.format(max_number_correct))

scores_arrays = []

# percent correct for each element in the array
# an array of scores for each test taker
for num_correct in num_correct_arrays:
    scores_array = num_correct / num_questions * 100
    scores_arrays.append(scores_array)
    print('Percent correct array:\n{}\n'.format(scores_array))

# another array with scores from both forms
scores_for_keyA_and_keyB = np.hstack((scores_arrays[0],
                                      scores_arrays[1]))
# best score of the forms
max_scores = scores_for_keyA_and_keyB.max(axis=1)

# this is a really weird approach to finding the max value
# create new array with scores for each key
stacked_scores = np.hstack((scores_arrays[0], scores_arrays[1]))
# make a boolean mask to find largest value
keyA_mask = scores_arrays[0] > scores_arrays[1]
# invert mask for key B
keyB_mask = keyA_mask.copy()
# use bitwise xor to flip boolean values
keyB_mask ^= True
# now sum the product of masks and data, but ignore last two rows (keys)
best_scores_array = (keyA_mask * scores_arrays[0] + keyB_mask *
                     scores_arrays[1])

correct_per_question_arrays = []

# use the key masks to only collect the best responses to questions
# assumes last two rows are keys and disregards them in calculation
best_answers_array = keyA_mask * scored_arrays[0] + \
                     keyB_mask * scored_arrays[1]

# sums over columns to get number of times question answered correctly
correct_per_question_array = best_answers_array.sum(axis=0, keepdims=True)
print('Number of times each question answered correctly:\n{}\n'.format(
    correct_per_question_array))

# median score for test takers
median_score = np.median(best_scores_array)
print('The median exam score is {}\n'.format(median_score))

# ------------------------------------------ #

# top performer mask
# top_array_mask = np.array(best_scores_array >= median_score, dtype=int)
top_array_mask = best_scores_array >= median_score
print('examinees who scored greater than or equal to median:\n'
      '{}\n'.format(top_array_mask))

# number of top performing students
num_top_scorers = top_array_mask.sum()
print('{} top performers\n'.format(num_top_scorers))

# bottom performer mask
bottom_array_mask = best_scores_array < median_score
# print('bottom examinees mask:\n{}\n'.format(bottom_array_mask))

# number of top performing students
num_bottom_scorers = bottom_array_mask.sum()
print('{} bottom performers\n'.format(num_bottom_scorers))

# data for examinees with top 50% score
top_array = top_array_mask * best_answers_array
# print('top examinees array:\n{}\n'.format(top_array))

# data for examinees with bottom 50% score
bottom_array = bottom_array_mask * best_answers_array
# print('bottom examinees array:\n{}\n'.format(bottom_array))

# correct questions for top performers
num_correct_top_array = top_array.sum(axis=0, keepdims=True)
print('Number of correct answers for top performers:\n'
      '{}\n'.format(num_correct_top_array))

# correct questions for bottom performers
num_correct_bottom_array = bottom_array.sum(axis=0, keepdims=True)
print('Number of correct answers for bottom performers:\n'
      '{}\n'.format(num_correct_bottom_array))

# array of discrimination values for each question
item_discrimination_array = \
    (num_correct_top_array - num_correct_bottom_array) / num_top_scorers
print('array of item discrimination values:\n'
      '{}\n'.format(item_discrimination_array))

# dataframe for the discrimination results (to make combining easier)
# naming the `index` means I'll have a row heading
item_discrimination_frame = pd.DataFrame(item_discrimination_array,
                                         columns=exam_data.columns[3:],
                                         index=['item discrimination'])

# the size of the `best_scores_array` lets us know how many test takers
item_difficulty_array = correct_per_question_array / num_test_takers * 100
print('Array of item difficulty percentages:\n'
      '{}'.format(item_difficulty_array))

# dataframe version
item_difficulty_frame = pd.DataFrame(item_difficulty_array,
                                     columns=exam_data.columns[3:],
                                     index=['item difficulty'])

item_analysis_frame = pd.concat([item_difficulty_frame,
                                item_discrimination_frame])

# code to export csv file with item analysis data
# item_analysis_frame.to_csv('~/item_analysis.csv')

# todo: might want to keep all of the data generated in an array for each
# student or some other place for later analysis

# todo: same analysis for exam distractors

# experimenting

# convert scores to pd data frame
best_scores_frame = pd.DataFrame(data=best_scores_array, columns=['score'])

# add scores to response data
exam_data_scored = pd.concat([exam_data[:28], best_scores_frame], axis=1)

# export to csv file that doesn't include an index column
# exam_data_scored[['OrgDefinedId', 'score']].to_csv('~/csvfile.csv',
# index=False)
