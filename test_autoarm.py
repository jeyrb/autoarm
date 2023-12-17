from unittest import mock
from appdaemon_testing.pytest import automation_fixture
from autoarm import AlarmArming

PANEL='alarm_control_panel.test_panel'

def test_not_occupied(hass_driver,autoarm: AlarmArming):
    with hass_driver.setup():
         hass_driver.set_state("person.tester_bob", "away")
    assert autoarm.is_occupied() is False

def test_occupied(hass_driver,autoarm: AlarmArming):
    with hass_driver.setup():
         hass_driver.set_state("person.tester_bob", "home")
    assert autoarm.is_occupied() is True

def test_day(hass_driver,autoarm: AlarmArming):
    with hass_driver.setup():
         hass_driver.set_state("sun.sun", "above_horizon")
    assert autoarm.is_night() is False

def test_reset_at_home_sets_night(hass_driver,autoarm: AlarmArming):
    with hass_driver.setup():
         hass_driver.set_state("sun.sun", "below_horizon")
         hass_driver.set_state("person.tester_bob", "home")
    assert autoarm.reset_at_home() == 'armed_night'

def test_reset_at_home_sets_home(hass_driver,autoarm: AlarmArming):
    with hass_driver.setup():
         hass_driver.set_state("sun.sun", "above_horizon")
         hass_driver.set_state("person.tester_bob", "home")
    assert autoarm.reset_at_home() == 'armed_home'

def test_unforced_reset_leaves_disarmed(hass_driver,autoarm: AlarmArming):
    with hass_driver.setup():
         hass_driver.set_state("sun.sun", "above_horizon")
         hass_driver.set_state("person.tester_bob", "home")
         hass_driver.set_state(PANEL, "disarmed")
    assert autoarm.reset_at_home(force_arm=False) is None

def test_forced_reset_sets_armed_home_from_disarmed(hass_driver,autoarm: AlarmArming):
    with hass_driver.setup():
         hass_driver.set_state("sun.sun", "above_horizon")
         hass_driver.set_state("person.tester_bob", "home")
         hass_driver.set_state(PANEL, "disarmed")
    assert autoarm.reset_at_home(force_arm=True) == 'armed_home'

@automation_fixture(
    AlarmArming,
    args={
                'occupants':['person.tester_bob'],
                'alarm_panel':PANEL
   
        },
)
def autoarm() -> AlarmArming:
    pass
