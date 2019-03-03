import pytest
import sys
import os


# this code allows us to import the functions file
sys.path.insert(0, './4-python scripts/functions/')
print(os.getcwd())

from grader_functions import *
# from bubblesheet_grader import course_details


@pytest.fixture()
def create_class():
    classdata = ClassData()

    return classdata

@pytest.fixture()
def populated_create_class():
    classdata = ClassData()

    # 30 questions for testing
    classdata.number_of_questions = 30

    return classdata

def test_ClassDataInitialized(create_class):

    classdata = create_class

    assert isinstance(classdata, ClassData)


def test_CourseDetailsFunction(create_class):

    assert type(course_details()) is dict


# def test_ListPickerHelperFunction():
#
#     dictionary = {'1401_6303': 'PHYS-1401 6303 roster.csv',
#                   '1410_6301': 'PHYS-1410 6301 roster.csv'}
#
#     assert type(list_picker(dictionary)) is str


# list picker tests
def test_ListPickerHelperFunctionDictionary(monkeypatch):
    """Test to see if the second item is selected from a dictionary
    """

    dictionary = {'1401_6303': 'PHYS-1401 6303 roster.csv',
                  '1410_6301': 'PHYS-1410 6301 roster.csv'}

    # this allows us to simulate a user input value given by the lambda
    # function. sys.input() doesn't work during unit testing.
    monkeypatch.setattr('builtins.input',
                        lambda x: 1)

    result = list_picker(dictionary)

    # ensure that code can handle integer as string type
    monkeypatch.setattr('builtins.input',
                        lambda x: '1')

    result_str = list_picker(dictionary)

    assert result == ('1410_6301', 'PHYS-1410 6301 roster.csv')
    assert result_str == ('1410_6301', 'PHYS-1410 6301 roster.csv')


def test_ListPickerHelperFunctionList(monkeypatch):
    """Test to see if the second item is selected from a list of possible
    items, opposed to a dict.
    """

    selection_list = ['selection 0',
                      'selection 1',
                      'selection 2']

    monkeypatch.setattr('builtins.input',
                        lambda x: 1)

    result = list_picker(selection_list)

    assert result == 'selection 1'


def test_ListPickerHelperFunctionListError(monkeypatch):
    """Test to see if the second item is selected from a list of possible
    items, opposed to a dict.

    - out of range
    - float instead of integer
    - string instead of integer
    """

    selection_list = ['selection 0',
                      'selection 1',
                      'selection 2']

    monkeypatch.setattr('builtins.input',
                        lambda x: 3)

    result = list_picker(selection_list)

    # check for float response
    monkeypatch.setattr('builtins.input',
                        lambda x: 3.)

    non_integer = list_picker(selection_list)

    # check for str response
    monkeypatch.setattr('builtins.input',
                        lambda x: 'tim')

    str_input = list_picker(selection_list)

    assert result is None
    assert non_integer is None
    assert str_input is None


# def test_rosters_populated():
# #     assert False


def test_get_num_questions(create_class):
    """Can you get the number of questions from the ClassData instance?

    :param create_class:
    :return:
    """
    classdata = create_class

    assert type(classdata.get_num_of_ques()) is int

    assert classdata.get_num_of_ques() == 0

    classdata.number_of_questions = 30
    assert classdata.get_num_of_ques() == 30


def test_grade_exam(populated_create_class, monkeypatch):
    """

    :param populated_create_class:
    :return:
    """

    monkeypatch.setattr('builtins.input',
                        lambda x: 1)

    classdata = populated_create_class

    assert classdata.grade_exam() is True


def test_roster_data_path(monkeypatch):
    """Does the data path helper function actually work?
    """

    monkeypatch.setattr('builtins.input',
                        lambda x: 1)

    roster_path = './4-python scripts/data/PHYS-1410 6301 roster.csv'
    data_path = './4-python scripts/results/' \
                'scanned bubblesheets formatted.csv'

    assert roster_data_path('roster') == roster_path
    assert roster_data_path('data') == data_path


def test_grade_exam(create_class, monkeypatch):
    # select 1401 data
    monkeypatch.setattr('builtins.input',
                        lambda x: 0)

    classdata = create_class

    # right now a True return means method executed without error
    assert classdata.grade_exam()

def test_ingest_exam_keys():
    # classdata = create_class

    correct_path_a = './exam keys/keyA.pdf'
    correct_path_b = './exam keys/keyB.pdf'

    assert roster_data_path('keyA') == correct_path_a
    assert roster_data_path('keyB') == correct_path_b


def test_convert_pdf_to_txt():
    path = roster_data_path('keyA')

    correct_path = './exam keys/keyA.pdf'

    assert type(convert_pdf_to_txt(path)) is str