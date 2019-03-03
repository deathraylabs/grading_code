""" Collection of functions to help generate grade processing scripts
for jMetrik.
"""

import re
import datetime

# imports for convert_pdf_to_txt
import io
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage


def get_metadata_from_user():
    """ User needs to enter metadata that will be used to populate the jmetrik template
    file.

    :return exam_metadata: list of tuples containing metadata
    """

    # prompt user for metadata

    # semester = str(input('What semester is it? ')) # logic used below instead
    course_number = str(input("What's the course number (ex: 2425)? "))
    section_number = str(input("What's the section number? "))
    exam_number = 'EXAM_' + str(input('What is the exam number? '))

    # get the current year
    now = datetime.datetime.now()
    year_number = str(now.year)[2:]

    # automatically generate the semester abbreviation
    month_number = now.month
    if month_number >= 9 <= 12:
        semester = 'FA'
    elif month_number >= 1 <= 5:
        semester = 'SP'
    else:
        semester = 'S'

    # raw_data_path = input('What is the path to the formatted formscanner data? ')
    raw_data_path = '/Users/peej/Library/Mobile Documents/' \
                    'com~apple~CloudDocs/Lone Star College Classes/' \
                    'Lone Star Stuff/~scan and grade exams/' \
                    '4-python scripts/results/' \
                    'scanned bubblesheetsformatted.csv'

    exam_metadata = [('«exam number»', exam_number),
                     ('«semester»', semester),
                     ('«course number»', course_number),
                     ('«section number»', section_number),
                     ('«year»', year_number),
                     ('«file path»', raw_data_path)]

    return exam_metadata


def convert_pdf_to_txt(path):
    """ Function to convert a pdf document into a string of text for processing.

    :param path: path to pdf file (might need to escape spaces)
    :return: plain text
    """

    rsrcmgr = PDFResourceManager()
    retstr = io.StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = open(path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos = set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages,
                                  password=password,
                                  caching=caching,
                                  check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()

    return text


def clean_key(exam_key):
    """ Takes the raw text from the answer key, scrapes and selects only
    the question number and corresponding answer letter.

    :param exam_key: exam key from testgen pdf
    :return: list of tuples
    """

    # regular expression pattern
    pattern = re.compile(r'(\d+)\. ([A-Z, ]+)')

    # store all the data as a list
    all_data = pattern.findall(exam_key)

    return all_data


def get_number_of_questions(exam_key):
    """ Need to know how many questions were on the form in order to generate
    the proper jmetrik script. This function simply finds that number.

    :param exam_key:
    :return:
    """
    return len(exam_key)


def get_options_list(key_a, num_of_choices = []):
    """ Prompt user to enter number of options for each question in exam.
    User just enters last possible answer choice letter.

    :param key_a: cleaned key data
    :param num_of_choices: list of number of choices for each question
    :return: list of possible options for each question
    """
    # conversion dictionary
    answer_length = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5}

    # new list with number of answers
    updated_data = list()

    if num_of_choices == []:
        # check to see if an option list doesn't exist, if not prompt for items
        for question in key_a:
            prompt = 'last answer letter for question #' + str(question[0])
            possible_answers = str(input(prompt)).upper()
            updated_data.append((question[0], question[1],
                                 answer_length[possible_answers]))
    else:
        # hopefully this will merge key_a values with existing choice list
        for index in range(len(key_a)):
            updated_data.append((key_a[index][0], key_a[index][1],
                                 num_of_choices[index]))

    return updated_data


def combine_key_lists(formA_data, formB_data):
    """ Combines the two exam keys into one list

    :param formA_data: formA data plus options list
    :param formB_data: formB data, no options list
    :return: [ (ques #, ans-A, ans-B, # of options), ... ]
    """

    # return only form A data if the exam is a single form exam
    if  len(formB_data) == 0:
        return formA_data  # just use form A data if only one form

    # combine form A and B if both are present
    all_keys = map(lambda x, y: x[0:2] + y[1:] + x[2:], formA_data, formB_data)
    all_keys_list = list(all_keys)

    return all_keys_list


def scoring_key_generator(form, all_keys_list):
    """ Generates a scoring key that jmetrik can understand.

    :param form: exam key form letter
    :param all_keys_list: list that includes both keys
    :return: returns the scoring key that jmetrik can use
    """
    # this dictionary keeps track of questions associated with a given unique key
    scoring_key = dict()
    # conversion dictionary
    answer_length = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5}

    for question in all_keys_list:
        #     print(question)
        number_of_options = question[-1]
        key_list = [0, 0, 0, 0, 0, 0]
        key_list = key_list[:number_of_options]

        # possibility of multiple answer logic
        # correct answer or answers
        correct_answer = question[answer_length[form]].split(", ")

        # grab the correct answer for each item
        for answer in correct_answer:
            correct_answer_position = answer_length[answer] - 1
            key_list[correct_answer_position] = 1

        key_list = tuple(key_list)

        try:
            scoring_key[key_list].append('question000'[:-len(question[0])] + str(question[0]))
        except KeyError:
            scoring_key[key_list] = ['question000'[:-len(question[0])] + str(question[0])]

    return scoring_key


def scoring_string_generator(form, metadata, scoring_key):
    """ Function to generate the jmetrik scoring string text.

    :param form: form A or B
    :param metadata: metadata input from user
    :param scoring_key: scoring key generated earlier
    :return: string describing how to score data
    """

    # generate the database name from metadata user entered
    database = metadata[2][1] + metadata[1][1] + metadata[3][1]
    table = metadata[0][1] + form

    # helper function to get tuples in proper string format
    def list_to_string_list(list_of_strings):
        string = ''

        for item in list_of_strings:
            string += item + ','

        return string[:-1]

    number_of_keys = len(scoring_key)
    unique_keys = scoring_key.keys()

    # options dictionary to make life easier in string below
    options_dict = {2: '(A,B)',
                    3: '(A,B,C)',
                    4: '(A,B,C,D)',
                    5: '(A,B,C,D,E)'}

    # create the jmetrik key string
    scoring_string = 'scoring{\n'

    # database information
    scoring_string += '     data(db = {}, table = {});\n'.format(database, table)

    # number of keys
    scoring_string += '     keys(%s);\n' % str(number_of_keys)

    # generate the key string for each unique key
    for index, key in enumerate(unique_keys):
        # grab the questions that share the same key
        questions = list_to_string_list(scoring_key[key])
        # generate the 'scores' value from key (must get rid of spaces)
        scores = str(key).replace(" ", "")
        # generate the key item string
        #     scoring_string += '     key{}(variables = ({}), nr = null, scores = {}, \
        # options = {}, omit = null);\n'.format(index + 1, questions,
        #                                         str(key), options_dict[len(key)])
        scoring_string += '     key{}(options = {}, scores = {}, variables = ({}));\n'.format(index + 1,
                                                                                              options_dict[len(key)],
                                                                                              scores,
                                                                                              questions)

    # close up the string
    scoring_string += '}'

    return scoring_string


def populate_jmetrik_template(number_of_questions, scoring_string_A, scoring_string_B, exam_metadata):
    """ Grab the jmetrik script and populate it with the necessary details

    :param number_of_questions: how many questions were asked on the test?
    :param scoring_string_A: pass the scoring string for form A
    :param scoring_string_B:
    :param exam_metadata: need the metadata provided by user
    :return: string containing jmetrik script
    """

    # add metadata to the search and replace list
    search_replace = exam_metadata

    # add the scoring strings to the list
    search_replace.append(('«scoring A»', scoring_string_A))
    # check to see if there is a second form
    if not len(scoring_string_B) == 0:
        search_replace.append(('«scoring B»', scoring_string_B))

    ques_labels = str()

    # generate a string of question labels that were on the test
    for index in range(number_of_questions):
        number = str(index + 1)
        ques_label = 'question000'[:-len(number)] + number

        ques_labels += ques_label + ','

    # kill that last trailing comma
    ques_labels = ques_labels[:-1]

    # add question labels to the list
    search_replace.append(('«all question names»', ques_labels))

    # check to see if we are using 1 form or two forms
    if len(scoring_string_B) == 0:
        print("selecting 1 Form template")
        script_template = 'jmetric script template 1 form.txt'
    else:
        print('selecting 2 Form template')
        script_template = 'jmetric script template.txt'

    # grab a copy of the script template to work with
    # assumes code is always with script template
    with open(script_template, 'r') as file_object:
        jmetrik_script = file_object.read()

    # now find and replace all the metadata in the template
    edited_jmetrik_script = jmetrik_script

    # probably not a good idea but this is a destructive operation
    for pattern, repl in search_replace:
        edited_jmetrik_script = re.sub(pattern, repl, edited_jmetrik_script)

    return edited_jmetrik_script


def add_keys_as_student_data(formscanner_data_path, exam_key, form):
    """ Add the exam key to the scanned and cleaned bubblesheet csv file as if
    it were student data. This makes it easier to verify that the key was
    processed correctly by the PDF parser.

    :param formscanner_data_path: string corresponding to path to data
    :param exam_key: cleaned exam key data in the form of list of tuples
    :param form: name of the form corresponding to key

    :return: True if write was successful
    """

    # we'll append this to the CSV file
    data_string = '#9999999,' \
                  + str(form) + ',' \
                  + '"' + 'key' + str(form) + '"'

    # grab the answer values from the key and append to string
    for key_value in exam_key:
        data_string += ',' + key_value[1]

    data_string += '\n'

    # write the key data out to formscanner data file
    with open(formscanner_data_path,'a') as fileobj:
        fileobj.write(data_string)