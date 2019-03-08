""" Script to parse and score raw bubblesheet output from formscanner.

This refactored version changed the data model from purely functions
and global variables to an object oriented data model.

FormScanner question groups must use the following names:
response     => group name for question responses
OrgDefinedId => group name for student ID number
form         => group name for form letter
"""

import csv
import re
import pandas as pd
import numpy as np
import shelve

# imports for pdf conversion
import io
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

# import statements for helper functions
import pyperclip
import os
import sys


# Let the parser know how formscanner formats the data
csv.register_dialect('formscanner', delimiter=";")


class ClassData(object):
    """ This class is used to store the raw bubblesheet data
    for the class as output by the FormScanner app.

    requires import csv
    """

    def __init__(self, number_of_forms=2, id_length=7):
        self.number_of_questions = 0
        self.number_of_forms = number_of_forms
        self.id_length = id_length

        # this is the root directory of the project, change it if you end up
        # moving the directory to some other location.
        self.project_root_dir = '~/dev/grading_code/'

        # dict of lists containing the roster in the order it was saved
        self.roster_order = list()

        self.id_to_name = dict()
        self.id_to_randomid = dict()

        # contains all of the raw student responses
        self.raw_data = list()
        # contains all of the reformatted student response data
        self.class_data = list()

        self.all_fieldnames = list()
        self.ques_fieldnames = list()
        self.id_fieldnames = list()
        self.form_fieldname = list()

        # pandas dataframes that may be useful
        self.roster_df = pd.DataFrame()
        self.exam_keys_df = pd.DataFrame()
        self.responses_df = pd.DataFrame()
        self.scored_exam_df = pd.DataFrame()
        self.item_analysis_df = pd.DataFrame()

        # numpy arrays that may be useful

    def __str__(self):
        """ Generates a diagnostic report for troubleshooting.

        :return:
        """

        students_on_roster = len(self.id_to_name)
        line_break = '\n**********************************************\n\n'

        return (line_break
                + '%d students are listed on the roster\n'
                % students_on_roster
                + line_break
                )

    # todo: probably better implemented using pandas instead
    def ingest_roster(self, roster_file_path):
        """Import roster for comparison with student responses from FormScanner.

        Method ingests the roster and creates two dictionaries used to convert
        a student ID into a name and random ID number.
        """

        with open(roster_file_path) as csvfile:
            d2l_data_raw = csv.DictReader(csvfile)

            # get the column headings in case they are needed
            # column_headings = d2ldata_raw.fieldnames

            # roster_id = list()
            # roster_name = list()

            for row in d2l_data_raw:
                # basically just creating new dictionaries from the d2l export
                self.id_to_name[row['OrgDefinedId']] = row['Last Name'] + \
                                                       ', ' + row['First Name']

                self.roster_order.append((row['OrgDefinedId'],
                                          row['Last Name'] + ', ' +
                                          row['First Name']))

                try:
                    self.id_to_randomid[row['OrgDefinedId']] = \
                        row['random ID number Text Grade <Text>']
                except NameError:
                    print('no random ID in roster')

    def ingest_formscanner_data(self, formscanner_data_path):
        """ Import raw formscanner data from CSV file path provided.

        Method creates a dictionary for each row of data from the formscanner
        CSV file. Additionally all of the column headings are imported as
        lists for later use.

        :param formscanner_data_path: path to formscanner CSV data. Expected
        group names are 'form', 'response', and 'OrgDefinedId'.
        If the formscanner group names differ from these values (case
        sensitive) the ingest will not function properly.
        :return: None
        """

        with open(formscanner_data_path) as csvfile:
            # list of group names used with this scan
            group_names_dict = dict()

            # reader creates a dictionary mapping the header row to the
            # individual student entries using the dialect created above
            formscanner_raw = csv.DictReader(csvfile, dialect='formscanner')

            # grab all the column headings from CSV file
            self.all_fieldnames = formscanner_raw.fieldnames

            # get the unique group names eg '[OrgDefinedId]'
            for index, heading in enumerate(self.all_fieldnames):
                group_name = re.search(r'(.+)\.(.+)', heading)

                # prevent assignment of the None object to the dict (error)
                if group_name is not None:
                    # using dict ensures we don't duplicate group names
                    group_names_dict[group_name.group(1)] = index

            group_names = group_names_dict.keys()

            # get the number of questions based on number of items in cat.
            self.number_of_questions = (group_names_dict['response'] -
                                        group_names_dict['form'])

            # =========== separate out column headings =================

            # todo: Fix column headings code to be cleaner

            # list of column headings for questions
            # first we need to figure out how to slice the headings
            slice_max = group_names_dict['response'] + 1
            slice_min = slice_max - self.number_of_questions

            # now use the slice positions to get the question headings
            self.ques_fieldnames = formscanner_raw.fieldnames[slice_min:slice_max]

            # column headings for ID (to recover the correct order later)
            try:
                slice_max = group_names_dict['OrgDefinedId'] + 1
            except KeyError:
                slice_max = group_names_dict['OrgDefinedID'] + 1
            # slice_min = slice_max - self.id_length

            # assumes that the student ID length is always 7 numbers
            self.id_fieldnames = formscanner_raw.fieldnames[1:8]

            # column heading for the form letter
            # slice_max = group_names_dict['form'] + 1
            # slice_min = slice_max - 1

            self.form_fieldname = formscanner_raw.fieldnames[8]

            # reformat the student ID data and save to our list
            for row in formscanner_raw:
                self.raw_data.append(row)

        # check to see how many student bubblesheets were graded
        num_students_tested = len(self.raw_data)

        # text feedback regarding the scan
        print('\n%d student bubblesheet forms were processed\n'
              % num_students_tested)
        print('List of the formscanner group names:')

        for heading in group_names:
            print('    ' + heading)

        return

    def clean_formscanner_data(self):
        """ Method to clean up the formscanner data. Requires that data
        has already been ingested using the ingest_formscanner_data method.

        Method populates the class_data list, which is presumed to be empty.
        Method strips '[response] ' prefix from response names in
        ques_fieldnames
        """

        for student in self.raw_data:
            id_number = str()

            # concatenate student ID number
            for id_filename in self.id_fieldnames:
                # get rid of individual ID characters
                id_number += str(student.pop(id_filename))

            # #
            # print(id_number)

            # add the concatenated ID back to the dictionary
            student['OrgDefinedId'] = '#' + id_number

            # clean the 'form' heading
            student['form'] = student.pop(str(self.form_fieldname))

            # remove  '[response]' from question heading keys
            for question in self.ques_fieldnames:
                # want to cut off the 'response' part of the heading
                student[question[-len('[response] '):]] = student.pop(question)

            # assemble individual student dictionaries into a new list
            self.class_data.append(student)

            # #
            # print('list length is %d' % len(self.class_data))

        # also remove '[response] ' from question headings list
        short_ques_fieldnames = list()

        for question in self.ques_fieldnames:
            # cut off the 'responses' part of the heading
            short_ques_fieldnames.append(question[-len('[response] '):])

        # update the object question fieldnames heading list
        self.ques_fieldnames = short_ques_fieldnames

    def match_roster_to_responses(self):
        """ Method that matches names from roster to the submitted responses
        pulled in from
        FormScanner.

        Gets student name from roster based on the OrgDefinedId field from
        the response data.
        If no student is found with matching ID, the student data is recorded
        in a new list and the user is asked to identify the student using a
        prompt.

        :return: None
        """

        # storage for rewritten list
        temp_class_data_list = list()

        # list of students who provided incorrect student ID number
        temp_no_id_match = list()

        # roster list with no matching responses
        class_data_no_match = dict(self.id_to_name)

        for student in self.class_data:

            # get student ID from response data
            student_id = student['OrgDefinedId']

            # convert id number from responses to student name
            try:
                student_name = self.id_to_name[student_id]
            except KeyError:
                # student_name = 'No matching name on roster.'

                # add student to no match list
                temp_no_id_match.append(student)

                # head back to the top of the for loop and skip the rest
                continue

            # get random ID from student ID number
            try:
                student_random_id = self.id_to_randomid[student_id]
            except KeyError:
                student_random_id = 'none'

            # add data back to dictionary
            student['name'] = student_name
            student['random ID'] = student_random_id

            # add dictionary to temp list
            temp_class_data_list.append(student)

            # remove matched student from the no match list
            try:
                class_data_no_match.pop(student_id)
            except NameError:
                class_data_no_match[student_id] = 'id error'
                continue

        # rewrite the object class data list
        self.class_data = temp_class_data_list

        # print out a list of students from the roster with no matching
        # response data
        print('\nThe following %d students have no matching response data '
              'from the exam:'
              % len(class_data_no_match))

        class_data_no_match_list = list(class_data_no_match.items())

        for index, no_match in enumerate(class_data_no_match_list):
            print(str(index) + ' - ' + str(no_match))

        # print out list of response sheets with no matching name
        print('\nThere are %d ID number(s) not associated with enrolled '
              'students.\n'
              'Please select the index beside the roster ID number that '
              'corresponds\n'
              'to the correct student response ID and hit enter:'
              % len(temp_no_id_match))

        # select the correct value for the id
        for no_match in temp_no_id_match:
            matched_index = input(no_match['OrgDefinedId'] +
                                  ' corresponds to: ')
            selected_student = class_data_no_match_list[int(matched_index)]
            print('\nyou selected: ' + str(selected_student))
            print('\n\n')

            # first tuple entry is the selected student ID number
            no_match['OrgDefinedId'] = selected_student[0]

            # second tuple entry is the selected student name
            no_match['name'] = selected_student[1]

            # add our missing student back to the class data
            self.class_data.append(no_match)

    def write_to_csv(self, save_path):
        """ Method to output formatted data to a new CSV file.

        Use 'data_headings' to specify what data you would like to output
        to the
        CSV file.

        :param save_path: directory path and desired CSV file name for
        saved file
        :return: None
        """

        with open(save_path, 'w') as csvfile:

            # data headings for the output file
            data_headings = ['OrgDefinedId', 'random ID', 'form', 'name'] + \
                             self.ques_fieldnames

            # use the list of column headings for the fieldnames
            # extrasaction parameter determines what happens if key is in dict
            # but not in fieldnames
            writer = csv.DictWriter(csvfile, fieldnames=data_headings,
                                    extrasaction='ignore')

            # header row first, then the rest
            writer.writeheader()
            writer.writerows(self.class_data)

    def ingest_exam_keys(self, keys=('keyA', 'keyB')):
        """Convert the pdf keys from testgen into a pandas dataframe
        representation.

        :param: the keys parameter is used for testing
        :return: returns the DataFrame with exam answer keys
        """

        raw_data = list()

        # regular expression pattern
        pattern = re.compile(r'(\d+)\. ([A-Z, ]+)')

        for key in keys:
            exam_key = convert_pdf_to_txt(self.roster_data_path(key))

            raw_frame = pd.DataFrame(pattern.findall(exam_key), columns=(
                'ques number', f'{key} answer'))

            # store all the data as a list
            raw_data.append(raw_frame)

        # merge the key data into a new dataframe
        raw_data_frame = pd.merge(raw_data[0], raw_data[1], on='ques number')

        raw_data_frame.set_index('ques number')
        self.exam_keys_df = raw_data_frame

        return raw_data_frame

    def get_num_of_ques(self):
        """Number of questions in the test. Requires formscanner data cleaned
        first.

        :return:
        """

        return int(self.number_of_questions)

    def get_root_dir(self):
        """Gets the current root directory
        """

        return self.project_root_dir

    # todo: this code needs to be more fully integrated into class
    def grade_exam(self):
        """Custom grading code
        """
        # todo: Need to check for state variables present

        responses_df = self.responses_df

        # convert to numpy array for manipulation ease
        responses_np = responses_df.to_numpy()

        # create a new array that just includes response data
        stripped_responses_np = responses_np[:, 4:]

        # probably a better way to do this but it will work with existing
        exam_key_a = self.exam_keys_df['keyA answer'].to_numpy()
        exam_key_b = self.exam_keys_df['keyB answer'].to_numpy()

        # might as well just score each test against both keys
        exam_keys = (exam_key_a, exam_key_b)

        # list to contain scored arrays
        scored_arrays = []

        # check each item against the key for both keys
        for key in exam_keys:
            scored = key == stripped_responses_np
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

        # ------- select the exams scored against best key --------#

        scored_exam_np = np.array([])

        # Take the array scored against form A and multiply with the bool
        # array that compares total score of A against B then repeat for B.
        #
        # This selects the row with best total score from two keys and then
        # inserts it into the scored_exam_np array.
        scored_exam_np = (scored_arrays[0] *
                          (num_correct_arrays[0] >= num_correct_arrays[1])
                          +
                          scored_arrays[1] *
                          (num_correct_arrays[0] < num_correct_arrays[1])
                          )

        # probably redundant sum of correct responses
        number_correct_np = scored_exam_np.sum(axis=1, keepdims=True)

        # todo: might add a method to drop specific questions
        # percent correct, then rounded to integer
        percent_correct_np = (number_correct_np / int(num_questions) * 100)
        percent_correct_np = percent_correct_np.round(decimals=0)

        # note that these results are saved as integer values
        scores_df = pd.DataFrame(np.hstack((number_correct_np,
                                            percent_correct_np)),
                                 columns=['number correct',
                                          'percent correct'],
                                 dtype='int')

        # -------------- save scored exam array to class ------------- #

        # first need to grab the column titles for questions
        responses_headings = len(list(responses_df))
        ques_headings = list(responses_df)[(responses_headings -
                                            num_questions):]
        student_data_headings = list(responses_df)[:-num_questions]
        # then convert to pandas dataframe
        scored_exam_df = pd.DataFrame(scored_exam_np, columns=ques_headings)
        # finally combine student data with it
        scored_exam_df = pd.concat([responses_df[student_data_headings],
                                    scored_exam_df],
                                    axis=1)
        # tack on the scores
        scored_exam_df = pd.concat([scored_exam_df, scores_df],
                                   axis=1)

        # update the state variable
        self.scored_exam_df = scored_exam_df

        # array containing number of correct answers graded against each key
        correct_for_key_a_and_key_b = np.hstack((num_correct_arrays[0],
                                                 num_correct_arrays[1]))
        print('Array of number correct for each key:\n'
              '{}\n'.format(correct_for_key_a_and_key_b))

        # grab the largest number of correct items between keys
        max_number_correct = correct_for_key_a_and_key_b.max(axis=1)
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
        # scores_for_key_a_and_key_b = np.hstack((scores_arrays[0],
        #                                         scores_arrays[1]))
        # best score of the forms
        # max_scores = scores_for_key_a_and_key_b.max(axis=1)

        # this is a really weird approach to finding the max value
        # create new array with scores for each key
        # stacked_scores = np.hstack((scores_arrays[0], scores_arrays[1]))

        # make a boolean mask to find largest value
        key_a_mask = scores_arrays[0] > scores_arrays[1]

        # invert mask for key B
        key_b_mask = key_a_mask.copy()

        # use bitwise xor to flip boolean values
        key_b_mask ^= True

        # now sum the product of masks and data, but ignore last two rows (keys)
        best_scores_array = (key_a_mask * scores_arrays[0] + key_b_mask *
                             scores_arrays[1])

        # use the key masks to only collect the best responses to questions
        # assumes last two rows are keys and disregards them in calculation
        best_answers_array = (key_a_mask * scored_arrays[0] +
                              key_b_mask * scored_arrays[1])

        # sums over columns to get number of times question answered correctly
        correct_per_question_array = best_answers_array.sum(axis=0,
                                                            keepdims=True)
        print('Number of times each question answered '
              'correctly:\n{}\n'.format(correct_per_question_array))

        # median score for test takers
        median_score = np.median(best_scores_array)
        print('The median exam score is {}\n'.format(median_score))

        # ----------------- item analysis ------------------------- #

        # top performer mask
        # top_array_mask = np.array(best_scores_array >= median_score,
        #                           dtype=int)
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
        item_discrimination_frame = \
            pd.DataFrame(item_discrimination_array,
                         columns=responses_df.columns[3:],
                         index=['item discrimination'])

        # the size of the `best_scores_array` lets us know how many test takers
        item_difficulty_array = \
            correct_per_question_array / num_test_takers * 100
        print('Array of item difficulty percentages:\n'
              '{}'.format(item_difficulty_array))

        # dataframe version
        item_difficulty_frame = pd.DataFrame(item_difficulty_array,
                                             columns=responses_df.columns[3:],
                                             index=['item difficulty'])

        item_analysis_frame = pd.concat([item_difficulty_frame,
                                         item_discrimination_frame])

        # save this to the state of the object
        self.item_analysis_df = item_analysis_frame

        # code to export csv file with item analysis data
        # item_analysis_frame.to_csv('~/item_analysis.csv')

        # todo: might want to keep all of the data generated in an array
        # for each student or some other place for later analysis

        # todo: same analysis for exam distractors

        # export to csv file that doesn't include an index column
        scored_exam_data[['OrgDefinedId', 'score']].to_csv(
                            '~/Desktop/graded exams and ID numbers.csv',
                            index=False)

        return True

    # todo: would be better to save state to sqlite db
    def save_state_to_db(self):
        """Method saves current state to shelve database for easy reuse
        """

        # tuple containing state variables you'd like to save
        state_variables = {'roster_df': self.roster_df,
                           'exam_keys_df': self.exam_keys_df,
                           'scored_exam_df': self.scored_exam_df,
                           'item_analsis_df': self.item_analysis_df,
                           'responses_df': self.responses_df}

        with shelve.open('saved state') as db:
            for variable_name, state_variable in state_variables.items():
                # todo: needs something to catch error
                db[variable_name] = state_variable

        return

    def get_state_from_db(self):
        """Method loads last saved state to class variables
        """
        pass

    def change_root_dir(self, project_root_dir):
        """Method changes the project root directory from the initilization
        value to the new path
        """

        # todo: check to ensure that value passed is actually valid path
        self.project_root_dir = project_root_dir

        return

    def roster_data_path(self, desired_path):
        """Helper function that generates a path to the class roster, exam
        data, and exam keys.
        :param desired_path: 'roster', 'data', 'keyA', 'keyB'
        :return:
        """
        # use project root directory for relative paths
        root_dir = self.project_root_dir

        # directory path to exam keys
        if (desired_path == 'keyA' or
                desired_path == 'keyB' or
                desired_path == 'test_keyA' or
                desired_path == 'test_keyB'):

            keys_data_path = os.path.join(root_dir, 'exam keys/',
                                          f'{desired_path}.pdf')

            return keys_data_path

        elif desired_path is 'data':
            exam_data_path = os.path.join(root_dir,
                                          '4-python scripts/results/',
                                          'scanned bubblesheets '
                                          'formatted.csv')
            return exam_data_path
        elif desired_path is 'roster':
            # course roster dictionary
            rosters = {'1401_6303': 'PHYS-1401 6303 roster.csv',
                       '1410_6301': 'PHYS-1410 6301 roster.csv'}

            course_number, roster_file_name = list_picker(rosters)

            # get the path from the course number
            # assuming that data directory is above current working directory
            roster_file_path = os.path.join(root_dir, '4-python scripts/data/',
                                            roster_file_name)

            return roster_file_path

        return

    def to_d2l_gradebook(self):
        """Method creates a csv file that can be directly imported into the
        D2L gradebook.
        """

        pass

    def to_d2l_feedback(self):
        """Method creates a csv file that can be imported into d2l as student
        feedback"""

        pass


""" Helper functions

These are useful functions for carrying out the steps required to scan a
bubblesheet graded exam.
"""


def create_dir():
    """ Function that takes the exam directory path copied to the clipboard
    and generates the additional directory structure required to process
    exam data. User must copy the correct path to the clipboard *before*
    running this part of the script.

    :return: Returns the tuple (exam_dir, parent_dir, data_dir). 'exam_dir'
    is the current exam directory, 'parent_dir' is the directory that the
    exam directory sits in, and 'data_dir' is the directory used to store
    data processed along the way.
    """

    # grab the exam path that should be in the clipboard
    exam_dir = pyperclip.paste()

    # # change working directory to the path we copied, with exception handling
    # proper_dir = False  # condition to exit while loop

    # try to get user to input correct path to directory until right or quit
    while not os.path.isdir(exam_dir):
        exam_dir = input('The directory could not be found.'
                         'Copy directory here to continue or type quit:\n')
        if exam_dir == 'quit':  # exit execution of script
            sys.exit('user exited')

    # now to also get the parent directory
    parent_dir = os.path.abspath('..')

    # create the exam data directory

    data_dir = os.path.dirname(exam_dir) + ' data'  # directory string

    # pre-existing directories will throw an error
    try:
        os.makedirs(data_dir)
    except FileExistsError:
        choice = input("Directory exists, proceed or quit?\n")
        if choice == 'quit':  # if quit, stop execution of script
            sys.exit('user exited')

    # debugging statements
    print(exam_dir)
    print(parent_dir)
    print(data_dir)

    return exam_dir, parent_dir, data_dir


def course_details():
    """Helper function to create and get paths to data.
    """

    # course roster dictionary
    rosters = {'1401_6303': 'PHYS-1401 6303 roster.csv',
               '1410_6301': 'PHYS-1410 6301 roster.csv'}

    return rosters


def list_picker(selection_list):
    """Helper function to select an item from a list of items. Function
    displays the coices available to user, who then selects an option.

    :returns type provided to it
    """

    # treat dictionary differently than list or tuple
    if type(selection_list) is dict:
        selection_items = list(selection_list.items())
    else:
        selection_items = selection_list

    # one line buffer to prettify
    print('\n\n')
    print('Please select from one of the following options:\n')

    for index, item in enumerate(selection_items):
        print('{}. {}'.format(str(index), str(item)))

    try:
        selection = int(input('Item Number: '))
    except ValueError:
        print('Please only enter integer values.')
        return

    # check for numerical values
    try:
        # if numerical, then ensure it's within range
        if selection < len(selection_items):
            selected_item = selection_items[selection]
        else:
            print('The number entered is not a valid option.')
            return
    except TypeError:
        print('Please only enter integer values.')
        return

    return selected_item


def shelve_data(data_to_shelve, variable_name):
    """Function to store data for easy retrieval later on.
    """
    with shelve.open('grading_code_temp_db.db') as db:
        try:
            db[variable_name] = data_to_shelve
        except KeyError:
            print('***** data was NOT shelved! *****')

    return


def convert_pdf_to_txt(path):
    """ Function to convert a pdf document into a string of text for processing.

    :param path: path to pdf file (might need to escape spaces)
    :return: plain text
    """

    abs_path = os.path.expanduser(path)

    rsrcmgr = PDFResourceManager()
    retstr = io.StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = open(abs_path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos = set()

    for page in PDFPage.get_pages(fp, pagenos,
                                  maxpages=maxpages,
                                  password=password,
                                  caching=caching):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()

    return text
