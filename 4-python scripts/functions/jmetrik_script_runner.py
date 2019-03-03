#! /Users/peej/anaconda/envs/grading

import jmetrik_functions as jf
import shelve
import pyperclip as cb

metadata = jf.get_metadata_from_user()
formscanner_data_path = metadata[5][1]

# get the exam keys into memory
key_a = jf.convert_pdf_to_txt('exam keys/keyA.pdf')
key_a = jf.clean_key(key_a)
# add key a to the formscanner data csv file
jf.add_keys_as_student_data(formscanner_data_path, key_a, 'A')

# try to load second exam form if it exists
try:
    key_b = jf.convert_pdf_to_txt('exam keys/keyB.pdf')
    key_b = jf.clean_key(key_b)
except FileNotFoundError:
    print("Couldn't find keyB, assuming it's single form exam.")
    key_b = []    # set key_b to empty list which indicates 1 form mode

# add key B data to the formscanner data if it exists
if not key_b == []:
    jf.add_keys_as_student_data(formscanner_data_path, key_b, 'B')

num_ques = jf.get_number_of_questions(key_a)

# create or open a shelf file
shelfFile = shelve.open('stored_data')
# flag to see if shelf data exists
shelf_data_exists = True

# see if there's data already stored for us to work with
try:
    key_a_and_options = shelfFile['key_a_and_options']
except KeyError:
    shelf_data_exists = False

if shelf_data_exists:
    reuse_data = input("I found existing keyA data, do you want to use:\n"
                       "1. just the answer choice number data;\n"
                       "2. the full key;\n"
                       "n. neither?\n")
    if reuse_data == 'n':
        shelf_data_exists = False
    elif reuse_data == '2':
        shelf_data_exists = True
    elif reuse_data == '1':
        # just reuse the number of possible choices
        option_list = []
        for option in key_a_and_options:
            option_list.append(option[2])
        key_a_and_options = jf.get_options_list(key_a, option_list)
        shelfFile['key_a_and_options'] = key_a_and_options

# if there's no key data already, prompt user for it
if shelf_data_exists == False:
    # prompt user for number of options for each question
    key_a_and_options = jf.get_options_list(key_a)
    shelfFile['key_a_and_options'] = key_a_and_options

all_keys_list = jf.combine_key_lists(key_a_and_options,key_b)

# close the shelf file
shelfFile.close()

scoring_key_a = jf.scoring_key_generator('A', all_keys_list)
scoring_string_a = jf.scoring_string_generator('A', metadata, scoring_key_a)

# if there's no key B, no need to generate scoring strings.
if len(key_b) == 0:
    print("Don't need to generate scoring string B")
    scoring_string_b = ''
else:
    # generate scoring strings for form B
    scoring_key_b = jf.scoring_key_generator('B', all_keys_list)
    scoring_string_b = jf.scoring_string_generator('B', metadata, scoring_key_b)

# populate the scoring script with data generated so far
jmetrik_script = jf.populate_jmetrik_template(num_ques, scoring_string_a, scoring_string_b, metadata)

# add script to clipboard for easy access
cb.copy(jmetrik_script)

# path to location of generated script
script_path = '/Users/peej/Library/Mobile Documents/com~apple~CloudDocs/Lone Star College Classes/' \
              'Lone Star Stuff/~scan and grade exams/5-jMetrik scripts/jmetrik_script.txt'
# save script as text file
with open(script_path, 'w') as fileobj:
    fileobj.write(jmetrik_script)