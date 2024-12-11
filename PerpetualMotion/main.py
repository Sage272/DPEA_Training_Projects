# ////////////////////////////////////////////////////////////////
# //                     IMPORT STATEMENTS                      //
# ////////////////////////////////////////////////////////////////
import os
import math
import sys
import time
import threading

os.environ["DISPLAY"] = ":0.0"

from threading import Thread
from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import *
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.slider import Slider
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.animation import Animation
from functools import partial
from kivy.config import Config
from kivy.core.window import Window
from pidev.kivy import DPEAButton
from pidev.kivy import PauseScreen
from time import sleep
from dpeaDPi.DPiComputer import *
from dpeaDPi.DPiStepper import *

# ////////////////////////////////////////////////////////////////
# //                     HARDWARE SETUP                         //
# ////////////////////////////////////////////////////////////////
"""Stepper Motor goes into MOTOR 0 )
    Limit Switch associated with Stepper Motor goes into HOME 0
    One Sensor goes into IN 0
    Another Sensor goes into IN 1
    Servo Motor associated with the Gate goes into SERVO 1
    Motor Controller for DC Motor associated with the Stairs goes into SERVO 0"""


# ////////////////////////////////////////////////////////////////
# //                      GLOBAL VARIABLES                      //
# //                         CONSTANTS                          //
# ////////////////////////////////////////////////////////////////
ON = False
OFF = True
HOME = True
TOP = False
OPEN = False
CLOSE = True
YELLOW = 116/255, 165/255, 242/255, 1
BLUE = 0.917, 0.796, 0.380, 1
DEBOUNCE = 0.1
RAMP_LENGTH = 725


# ////////////////////////////////////////////////////////////////
# //            DECLARE APP CLASS AND SCREENMANAGER             //
# //                     LOAD KIVY FILE                         //
# ////////////////////////////////////////////////////////////////
class MyApp(App):
    def build(self):
        self.title = "Perpetual Motion"
        return sm

Builder.load_file('main.kv')
Window.clearcolor = (.1, .1, .1, 1) # (WHITE)



# ////////////////////////////////////////////////////////////////
# //                    SLUSH/HARDWARE SETUP                    //
# ////////////////////////////////////////////////////////////////
sm = ScreenManager()

# ////////////////////////////////////////////////////////////////
# //                       MAIN FUNCTIONS                       //
# //             SHOULD INTERACT DIRECTLY WITH HARDWARE         //
# ////////////////////////////////////////////////////////////////
	
# ////////////////////////////////////////////////////////////////
# //        DEFINE MAINSCREEN CLASS THAT KIVY RECOGNIZES        //
# //                                                            //
# //   KIVY UI CAN INTERACT DIRECTLY W/ THE FUNCTIONS DEFINED   //
# //     CORRESPONDS TO BUTTON/SLIDER/WIDGET "on_release"       //
# //                                                            //
# //   SHOULD REFERENCE MAIN FUNCTIONS WITHIN THESE FUNCTIONS   //
# //      SHOULD NOT INTERACT DIRECTLY WITH THE HARDWARE        //
# ////////////////////////////////////////////////////////////////

##### Motor Setup:

# Stepper:
dpiStepper = DPiStepper()
dpiStepper.setBoardNumber(0)
if not dpiStepper.initialize():
    print("Communication with the DPiStepper board failed.")

# Servo:
dpiComputer = DPiComputer()
dpiComputer.initialize()

#####

class MainScreen(Screen):
    max_ramp_speed = 200
    max_staircase_speed = 50
    rampSpeed = max_ramp_speed
    staircaseSpeed = max_staircase_speed
    yellow = YELLOW
    blue = BLUE

    auto_button_num = 0
    gate_button_num = 1
    ramp_button_num = 2
    staircase_button_num = 3

    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        #self.initialize()

    def toggleGate(self):
        servo_num = 0
        # disable all buttons if this isn't running as a part of the auto fn
        if not self.auto_running: Thread(target=self.disable_other_buttons).start() #self.disable_other_buttons(self.gate_button_num)
        dpiComputer.writeServo(servo_num, 180)
        sleep(0.25)
        dpiComputer.writeServo(servo_num, 0)
        # re-enable all buttons if this isn't running as a part of the auto fn
        if not self.auto_running: self.disable_other_buttons(False)

    def toggleStaircase(self):
        servo_num = 1
        # disable all buttons if this isn't running as a part of the auto fn
        if not self.auto_running: Thread(target=self.disable_other_buttons).start() #self.disable_other_buttons(self.staircase_button_num)
        staircase_speed = (round((self.staircaseSpeed / self.max_staircase_speed)) * 90) + 90
        dpiComputer.writeServo(servo_num, staircase_speed)
        sleep(7.5)
        dpiComputer.writeServo(servo_num, 90)
        # re-enable all buttons if this isn't running as a part of the auto fn
        if not self.auto_running: self.disable_other_buttons(False)
        
    def toggleRamp(self):
        stepper_num = 0
        # disable all buttons if this isn't running as a part of the auto fn
        if not self.auto_running: Thread(target=self.disable_other_buttons).start() #self.disable_other_buttons(self.ramp_button_num)
        # max of 10 rotations a second, min of 2
        num_revs = (8 * (self.rampSpeed/self.max_ramp_speed)) + 2
        steps = int(7 * 4.1429 * -1600)
        wait_to_finish_moving_flg = True
        # intial homing, incase ramp wasn't home yet
        self.home_ramp()
        if dpiComputer.readDigitalIn(dpiComputer.IN_CONNECTOR__IN_0) == 0:  # bottom sensor detects ball
            self.set_stepper_speed_by_revs_per_sec(num_revs, stepper_num)
            dpiStepper.enableMotors(True)
            # move to top
            dpiStepper.moveToRelativePositionInSteps(stepper_num, steps, wait_to_finish_moving_flg)
            # send to home, but also continue the other fns
            t = Thread(target=self.home_ramp)
            t.start()
        # re-enable all buttons if this isn't running as a part of the auto fn
        if not self.auto_running: self.disable_other_buttons(False)

    def home_ramp(self, dt=0):
        stepper_num = 0
        direction_for_homing = 1  # pos to go back home, neg to go to top
        steps_per_sec_for_homing = 10 * 1600  # ten revolutions
        max_steps_for_homing = int(7 * 4.1429 * 1600)
        # check if already home
        if not dpiStepper.getStepperStatus(stepper_num)[3]:
            dpiStepper.moveToHomeInSteps(stepper_num, direction_for_homing, steps_per_sec_for_homing, max_steps_for_homing)
            dpiStepper.enableMotors(False)

    auto_running = False
    def auto_button(self):
        #self.disable_other_buttons() #Thread(target=self.disable_other_buttons).start()
        if self.auto_running:
            self.auto_running = False
            Thread(target=lambda:self.update_auto_text(True)).start()
            # self.disable_other_buttons(False)
            # try: Clock.unschedule(self.check_for_ball)
            # except: pass
            # t = (Thread(target=self.update_auto_text))
            # t.start()
        else:
            self.auto_running = True
            t = (Thread(target=self.update_auto_text))
            t.start()


    def auto(self):
        self.disable_other_buttons(True, True)
        self.home_ramp()
        if dpiComputer.readDigitalIn(dpiComputer.IN_CONNECTOR__IN_0) == 0:  # bottom sensor detects ball
            self.toggleRamp()
            self.toggleStaircase()
            self.toggleGate()
            Clock.schedule_interval(self.check_for_ball, 0.05)

    def update_auto_text(self, ending=False):
        if ending:
            print("ending")
            self.ids.autoButton.text = "Ending"
        # has to call auto from here so that the UI will update the text
        elif self.auto_running:
            self.ids.autoButton.text = "End"
            self.auto()
        else:
            self.ids.autoButton.text = "Start"

    def check_for_ball(self, dt=0):
        if dpiComputer.readDigitalIn(dpiComputer.IN_CONNECTOR__IN_0) == 0:  # bottom sensor detects ball
            Clock.unschedule(self.check_for_ball)
            if self.auto_running:
                self.auto()
            else:
                self.update_auto_text()
                self.disable_other_buttons(False)

    def set_stepper_speed_by_revs_per_sec(self, revs_per_sec=2, stepper_num=0):
        dpiStepper.setSpeedInRevolutionsPerSecond(stepper_num, revs_per_sec)
        dpiStepper.setAccelerationInRevolutionsPerSecondPerSecond(stepper_num, revs_per_sec)

    def disable_other_buttons(self, disable=True, auto=False):
        # this function can enable all buttons if disable = False
        # auto, gate, ramp, staircase
        if not auto: self.ids["auto"].disabled = disable
        self.ids["gate"].disabled = disable
        self.ids["ramp"].disabled = disable
        self.ids["staircase"].disabled = disable

    def setRampSpeed(self, speed):
        self.rampSpeed = speed
        
    def setStaircaseSpeed(self, speed):
        self.staircaseSpeed = speed

    def resetColors(self):
        self.ids.gate.color = YELLOW
        self.ids.staircase.color = YELLOW
        self.ids.ramp.color = YELLOW
        self.ids.auto.color = BLUE
    
    def quit(self):
        print("Exit")
        MyApp().stop()

class BetterImageButton(ButtonBehavior, Image):
    current_button_id = 0 # static variable to keep track of all buttons
    button_id = 0 # the individual button id
    type = "BetterImageButton"
    def __init__(self, **kwargs):
        """
        Constructor for the better image button
        When using specify : id, source, size, position, on_press, on_release
    0    :param kwargs: Arguments supplied to super
        """
        super(BetterImageButton, self).__init__(**kwargs)
        Window.bind(mouse_pos=self.on_mouseover)
        self.size_hint = None, None
        self.keep_ratio = False
        self.allow_stretch = True
        self.size = 150, 150
        self.background_color = 0, 0, 0, 0
        self.background_normal = ''
        # handles the button_id, each button will have a unique number
        self.button_id = BetterImageButton.current_button_id
        BetterImageButton.current_button_id += 1
        # set the source here for all buttons to have the same image or in you .kv file for a button by button basis
        self.source = "WhiteButtonWithBlackBorder.png"

    # appends the button_id to the end of what self returns to allow for a complete individual reference to each button (the base self return is based off of position, meaning that two buttons could be mixed up)
    def __repr__(self):
        return super(BetterImageButton, self).__repr__() + str(self.button_id)

    # multiplies the two colors together by their individual rgba values
    def multiply_colors(self, color1, color2):
        return (color1[0] * color2[0], color1[1] * color2[1], color1[2] * color2[2], color1[3] * color2[3])


    # the (mouseover_color) or (mouseover_size) at the end shows which mouseover methods use them
    # if there is none, they both use them
    # any (mouseover_color) variable is also use by (mouseover_size) if both are True

    # determines what color to change the button to when hovered over (mouseover_color)
    hover_color = (0.875, 0.875, 0.875, 1.0)
    # SHOULD be set. if not set, the mouseover_size_method will default it to 13/12 the size of the button (mouseover_size)
    hover_size = None
    # determines how long the hover size animation will run (in seconds) (mouseover_size)
    hover_size_anim_duration = 0.125
    # Shouldn't be set, the mouseover methods will handle it (mouseover_color)
    original_color = (0.0, 0.0, 0.0, 0.0)
    # original_size and original_pos shouldn't need to be set because the mouseover_size_method will handle them (mouseover_size)
    # needs to be a large negative number to avoid a None type error (if I used None) or other potential design issues using another, closer to zero number
    original_size = original_pos = [-2147483647, -2147483647]
    # already_hovered is for either method, and handles the one time variable setting
    already_hovered = False
    # on_hover tells whether the button is currently being hovered over or not
    on_hover = False
    # controls whether the color is multiplied, or just set (mouseover_color)
    mouseover_multiply_colors = True
    # can be set to false to remove mouseover capabilities
    mouseover = True
    # determines which mouseover methods should run, one or both can be enabled
    mouseover_color = False
    mouseover_size = False
    # for handling new screens
    current_screen = ""
    previous_screen = ""

    # runs on everytime mouse is with in the window
    def on_mouseover(self, window, pos):
        if self.mouseover:
            # if both mouseover_color and mouseover_size are true, the mouseover_size_method handles that
            # if not, mouseover_size_method still works for just mouseover_size
            # mouseover_color_method works for just mouseover_color
            if self.mouseover_size:
                self.mouseover_size_method(window, pos)
            elif self.mouseover_color:
                self.mouseover_color_method(window, pos)

    def mouseover_color_method(self, window, pos):
        if not self.already_hovered:
            self.already_hovered = True
            self.original_color = self.color
        # runs when the button is being hovered over
        # it runs once, as soon as the cursor is OVER the button
        if not self.on_hover and self.collide_point(*pos):
            self.on_hover = True
            # multiplies the color (or just sets the color) to hover_color
            if self.mouseover_multiply_colors:
                self.color = self.multiply_colors(self.hover_color, self.color)
            else:
                self.color = self.hover_color
        # runs when not hovering over the button
        # it runs once, as soon as the cursor is OFF the button
        elif not self.collide_point(*pos) and self.on_hover:
            self.on_hover = False
            self.color = self.original_color

    def mouseover_size_method(self, widow, pos):
        # runs once per each button, even ones in other screens (than the one fist pulled up)
        # sets values for original_size, hover_size (if one wasn't set), and original_color
        if not self.already_hovered:
            self.already_hovered = True
            self.original_size = [self.size[0], self.size[1]]
            if not self.hover_size:
                self.hover_size = [self.size[0] * (13/12), self.size[1] * (13/12)]
            # for color handling
            # checks if the color should change too, and sets a default value if so
            if self.mouseover_color:
                self.original_color = self.color
        # runs each time a different screen is entered
        if self.current_screen != sm.current:
            self.previous_screen = self.current_screen
            self.current_screen = sm.current
            # ensures that when switching screens, the original_pos does not get set wrongly due to its animation
            # the == [-2147483647, -2147483647] check ensures that the original position is only set once
            # this can't be in the "run once only" if statement because it is on a screen not currently loaded, it will default to [0,0], not its actual position
            if self.original_pos == [-2147483647, -2147483647] and self in sm.current_screen.children: # looking at the new screens children, to see if the new button is in it
                self.original_pos = [self.x, self.y]
        # runs when the button is being hovered over
        # it runs once (because of on_hover), as soon as the cursor is OVER the button
        if not self.on_hover and self.collide_point(*pos):
            self.on_hover = True
            # for color handling
            # checks if the color should change too, and multiplies the color (or just sets the color) to hover_color
            if self.mouseover_color:
                if self.mouseover_multiply_colors:
                    self.color = self.multiply_colors(self.hover_color, self.color)
                else:
                    self.color = self.hover_color
            # animates the button to be the size of hover_size over the course of hover_size_anim_duration
            # the x/y part of the animation keeps the button centered on its original position (necessary because kivy size animations expand from the bottom left out)
            # I use the x/y values here and not center_x/y values, because when I did, the animation was too jittery
            on_hover_anim = Animation(x=(self.x + self.original_size[0]/2) - self.hover_size[0]/2, y=(self.y + self.original_size[1]/2) - self.hover_size[1]/2, size=(self.hover_size[0], self.hover_size[1]), duration=self.hover_size_anim_duration)
            on_hover_anim.start(self)
        # runs when not hovering over the button
        # it runs once (because of on_hover), as soon as the cursor is OFF the button
        elif not self.collide_point(*pos) and self.on_hover:
            self.on_hover = False
            # animates the button back to its original size, while keeping the position centered
            off_hover_anim = Animation(x=self.original_pos[0], y=self.original_pos[1], size=(self.original_size[0], self.original_size[1]), duration=self.hover_size_anim_duration)
            off_hover_anim.start(self)
            # for color handling
            # checks if the color should be changing too, and sets it back to the original color if so
            if self.mouseover_color:
                self.color = self.original_color

sm.add_widget(MainScreen(name = 'main'))

# ////////////////////////////////////////////////////////////////
# //                          RUN APP                           //
# ////////////////////////////////////////////////////////////////
if __name__ == "__main__":
    # Window.fullscreen = True
    # Window.maximize()
    MyApp().run()
