#! /usr/bin/python3

### Created by Chirag Khatri
### github.com/zvovov

import sched
import sys
import threading
import time
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException as WebDriverException
from selenium.common.exceptions import NoSuchElementException

config = {
    'chromedriver_path': "/usr/local/bin/chromedriver".format(os.environ['HOME']),
    'get_msg_interval': 5,  # Time (seconds). Recommended value: 5
    'colors': True,  # True/False. True prints colorful msgs in console
    'ww_url': "https://web.whatsapp.com/"
}

incoming_scheduler = sched.scheduler(time.time, time.sleep)
last_thread_name = ''
ult_msg = None # storing final incoming messafe data

# colors in console
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


try:
    def main():
        global last_thread_name

        if len(sys.argv) > 1:
            # Use a data directory so that we can persist cookies per session and not have to
            # authorize this application every time.
            # NOTE: This gets created in your home directory and can get quite large over time.
            # To fix this, simply delete this directory and re-authorize your WhatsApp Web session.
            chrome_data_dir_directory = "{0}/.chrome/data_dir/whatsapp_web_cli".format(os.environ['HOME'])
            if not os.path.exists(chrome_data_dir_directory):
                os.makedirs(chrome_data_dir_directory)

            driver_options = webdriver.ChromeOptions()
            driver_options.add_argument("user-data-dir={0}".format(chrome_data_dir_directory))

            # setting up Chrome with selenium
            driver = webdriver.Chrome(config['chromedriver_path'], chrome_options=driver_options)

            # open WW in browser
            driver.get(config['ww_url'])

            # prompt user to connect device to WW
            while True:
                isConnected = input(decorateMsg("\n\tPhone connected? y/n: ", bcolors.HEADER))
                if isConnected.lower() == 'y':
                    break

            assert "WhatsApp" in driver.title

            chooseReceiver(driver)

            # getting true name of contact/group
            last_thread_name = driver.find_element(By.XPATH, '//*[@id="main"]/header//span[contains(@dir, "auto")]').text

            # start background thread
            incoming_thread = threading.Thread(target=startGetMsg, args=(driver,))
            incoming_thread.start()

            while True:
                msg = input().strip()
                if len(msg) > 7 and 'sendto ' in msg[:7]:
                        chooseReceiver(driver, receiver=msg[7:])
                elif msg == 'stopsending':
                    print(decorateMsg("\tYou will only receive msgs now.\n\tPress Ctrl+C to exit.", bcolors.WARNING))
                    # TODO: stop the incoming_scheduler event
                    break
                else:
                    sendMsg(driver, msg)

        else:
            sys.exit(decorateMsg("\nError: Missing name of contact/group\npython chat.py <name>", bcolors.FAIL))

        # open all contacts page
        # driver.find_element(By.TAG_NAME, "button").click()


    def sendMsg(driver, msg):
        """
        Type 'msg' in 'driver' and press RETURN
        """
        # select correct input box to type msg
        input_box = driver.find_element(By.XPATH, '//*[@id="main"]//footer//div[contains(@class, "selectable-text")]')
        # input_box.clear()
        input_box.click()

        action = ActionChains(driver)
        action.send_keys(msg)
        action.send_keys(Keys.RETURN)
        action.perform()

    def startGetMsg(driver):
        """
        Start schdeuler that gets incoming msgs every get_msg_interval seconds
        """
        incoming_scheduler.enter(config['get_msg_interval'], 1, getMsg, (driver, incoming_scheduler))
        incoming_scheduler.run()

    def getMsg(driver, scheduler):
        """
        Get incoming msgs from the driver repeatedly
        """
        global last_printed_msg_id
        global ult_msg
        # print conversation name
        curr_thread_name = printThreadName(driver)

        # get incoming msgs
        all_msgs_text_only = driver.find_elements(By.XPATH, '//*[@id="main"]//div[contains(@class, "msg")]//span[contains(@dir, "ltr")]')

        # check if msg's exist
        try:
            first_msg = all_msgs_text_only[0]
        except IndexError: # thrown if there are no messages
            pass
        if first_msg: # if one or more messages exist
            is_first_incoming_msg = True # boolean flag used in for loop below ; if True: init msg_vector with msg, if False: append msg to msg_vector
            for i in range(0, len(all_msgs_text_only)):
                if isOutgoingMessage(all_msgs_text_only[i]):
                    pass
                else:
                    # build array of initial messages
                    msg_text = all_msgs_text_only[i].text
                    msg_sender = all_msgs_text_only[i].find_element_by_xpath('../..').get_attribute('data-pre-plain-text')
                    msg_data = [msg_sender, msg_text]
                    if is_first_incoming_msg:
                        msg_vector = [msg_data]
                        is_first_incoming_msg = False
                    else:
                        msg_vector.append(msg_data)

            if ult_msg: # final incoming message set in previous iteration ; so initial messages have already been fetched
                if ult_msg[0] == msg_vector[-1][0] and ult_msg[1] == msg_vector[-1][1]: # compare last fetched msg to last msg of previous iteration
                    pass # no new messages received
                else:
                    for i in range(len(msg_vector)-2, 0, -1):
                        if ult_msg[0] == msg_vector[i][0] and ult_msg[1] == msg_vector[i][1]:
                            break
                    for j in range(i+1, len(msg_vector)):
                        print(decorateMsg(msg_vector[j][0] + " " + msg_vector[j][1], bcolors.OKGREEN)) # print new messages

            ult_msg = [msg_vector[-1][0], msg_vector[-1][1]]

        # add the task to the scheduler again
        incoming_scheduler.enter(config['get_msg_interval'], 1, getMsg, (driver, scheduler,))

    def decorateMsg(msg, color=None):
        """
        Returns:
                colored msg, if colors are enabled in config and a color is provided for msg
                msg, otherwise
        """
        msg_string = msg
        if config['colors']:
            if color:
                msg_string = color + msg + bcolors.ENDC

        return msg_string

    def isOutgoingMessage (message):  # message = span containing the text message
        ggf = message.find_element_by_xpath('../../..') # find the span's "great-grandfather"
        try:
            # get the status icon
            ggf.find_element_by_xpath('..//div[contains(@class, "status-icon")]')
            # if no exception was thrown: status icon exists
            # => message is outgoing
            return True
        except NoSuchElementException:
            # Exception was thrown: there is no status icon
            # => message is incoming
            return False

    def printThreadName(driver):
        global last_thread_name
        curr_thread_name = driver.find_element(By.XPATH, '//*[@id="main"]/header//span[contains(@dir, "auto")]').text
        if curr_thread_name != last_thread_name:
            last_thread_name = curr_thread_name
            print(decorateMsg("\n\tSending msgs to:", bcolors.OKBLUE), curr_thread_name)
        return curr_thread_name

    def chooseReceiver(driver, receiver=None):
        # search name of friend/group
        friend_name = receiver if receiver else ' '.join(sys.argv[1:])
        input_box = driver.find_element(By.XPATH, '//*[@id="side"]//input')
        input_box.clear()
        input_box.click()
        input_box.send_keys(friend_name)
        input_box.send_keys(Keys.RETURN)
        printThreadName(driver)

    if __name__ == '__main__':
        main()

except AssertionError as e:
    sys.exit(decorateMsg("\n\tCannot open Whatsapp web URL.", bcolors.WARNING))

except KeyboardInterrupt as e:
    sys.exit(decorateMsg("\n\tPress Ctrl+C again to exit.", bcolors.WARNING))

except WebDriverException as e:
    sys.exit(print(e, decorateMsg("\n\tChromedriver Error. Read the above error (if any), then\n\tCheck if installed chromedriver version is compatible with installed Chrome vesion.", bcolors.WARNING)))
