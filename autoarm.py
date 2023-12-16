import appdaemon.plugins.hass.hassapi as hass
import datetime
import time

load_time=lambda v: datetime.datetime.strptime(v, '%H:%M:%S').time() if v else None
total_secs=lambda t: (t.hour*3600)+(t.minute*60)+t.second

OVERRIDE_STATES=('armed_away','armed_vacation')
ZOMBIE_STATES=('unknown','unavailable')

class AlarmArming(hass.Hass):

    def initialize(self):
        self.log('AUTOARM Initializing ...')
        delay_spec=load_time(self.args.get('arm_away_delay','00:00:00'))
        self.arm_away_delay=total_secs(delay_spec)
        self.auto_disarm=self.args.get('auto_disarm',False)     
        self.log('AUTOARM auto_disarm=%s, arm_delay=%s' % (self.auto_disarm,self.arm_away_delay))
        self.notify_profiles=self.args.get('notify',{})
        self.last_request=None

        self.listen_event(self.on_mobile_action,
                            'mobile_app_notification_action')

        self.initialize_alarm_panel()
        self.initialize_diurnal()
        self.initialize_occupancy()
        self.initialize_bedtime()
        self.initialize_buttons()   
        self.reset_at_home(force_arm=False)
        self.log('AUTOARM Initialized')

    def initialize_alarm_panel(self):
        ''' Set up automation for Home Assistant alarm panel
            See https://www.home-assistant.io/integrations/alarm_control_panel/
        '''
        self.alarm_panel=self.args.get('alarm_panel')
        self.listen_state(self.on_panel_change,self.alarm_panel)
        self.log('AUTOARM Auto-arming %s' % self.alarm_panel)

    def initialize_diurnal(self):
        ''' Configure handling of AppDaemon sunrise and sunset events '''
        self.sunrise_cutoff=load_time(self.args.get('sunrise_cutoff'))
        self.run_at_sunrise(self.on_sunrise)
        self.run_at_sunset(self.on_sunset)

    def initialize_occupancy(self):
        ''' Configure occupants, and listen for changes in their state '''
        self.occupants=self.args.get('occupants',())
        for person in self.occupants:
            self.listen_state(self.on_occupancy_change, person)
        self.log('AUTOARM Occupied: %s, Unoccupied: %s, Night: %s' % (self.is_occupied(),
                        self.is_unoccupied(),self.is_night()))

    def initialize_bedtime(self):
        ''' Configure usual bed time (optional) '''
        self.sleep_start=load_time(self.args.get('sleep_start'))
        self.sleep_end=load_time(self.args.get('sleep_end'))
        if self.sleep_start:
            self.run_daily(self.on_sleep_start, self.sleep_start)
        if self.sleep_end:
            self.run_daily(self.on_sleep_end, self.sleep_end)
        self.log('AUTOARM Bed time from %s->%s' % (self.sleep_start,self.sleep_end))
        
    def initialize_buttons(self):
        ''' Initialize (optional) physical alarm state control buttons '''
        self.button_device={}
        def setup_button(state,config_key,callback):
            self.button_device[state]=self.args.get(config_key)
            if self.button_device[state]:
                self.listen_state(callback,self.button_device[state],new="on")
                self.log('AUTOARM Configured %s button for %s' % (state,self.button_device[state]))
        setup_button('reset','reset_button_device',self.on_reset_button)
        setup_button('away','away_button_device',self.on_away_button)
        setup_button('disarm','disarm_button_device',self.on_disarm_button)
        setup_button('vacation','vacation_button_device',self.on_vacation_button)

    def is_occupied(self):
        return any(self.get_tracker_state(p) == 'home' for p in self.occupants )

    def is_unoccupied(self):
        return all(self.get_tracker_state(p) != 'home' for p in self.occupants )

    def is_night(self):
        return self.get_tracker_state('sun.sun') == 'below_horizon'

    def armed_state(self):
        return self.get_tracker_state(self.alarm_panel)

    def on_panel_change(self, entity, attribute, old, new, kwargs):
        self.log('AUTOARM Panel Change: %s,%s,%s,%s,%s' % (entity,attribute,old,new,kwargs))
        if new in ZOMBIE_STATES:
            self.log('AUTOARM Dezombifying %s ...' % new)
            self.reset_at_home()
        else:
            message="Home Assistant alert level now set from %s to %s" % ( old,new)
            self.notify_flex(message,title="Alarm now %s" % new,profile='quiet')
       
    def on_occupancy_change(self, entity, attribute, old, new, kwargs):
        existing_state=self.armed_state()
        self.log('AUTOARM Occupancy Change: %s,%s,%s,%s,%s' % (entity,attribute,old,new,kwargs))
        if self.is_unoccupied() and existing_state not in OVERRIDE_STATES:
            self.arm("armed_away")
        elif self.is_occupied() and existing_state=='armed_away':
            self.reset_at_home()

    def reset_at_home(self,force_arm=True,hint_arming=None):
        existing_state=self.armed_state()
        if existing_state != 'disarmed' or force_arm:
            if self.armed_state() not in OVERRIDE_STATES:
                if hint_arming:
                    return self.arm(hint_arming)
                elif self.is_night():
                    return self.arm('armed_night')
                else:
                    return self.arm('armed_home')

    def delayed_arm(self,cbargs):
        self.log('Delayed_arm %s' % cbargs)
        reset=cbargs.get('reset',False)
        requested_at=cbargs.get('request_time')
        arming_state=cbargs.get('arming_state')
        if self.last_request is not None and requested_at is not None:
            if self.last_request > requested_at:
                self.log('AUTOARM Cancelling delayed request for %s since subsequent manual action' % arming_state)
                return
            else:
                self.log('AUTOARM Delayed execution of %s requested at %s' % ( arming_state, requested_at))
        if reset:
            self.reset_at_home(force_arm=False, hint_arming=arming_state)
        else:
            self.arm(arming_state=arming_state)

    def arm(self,arming_state=None):
        existing_state=self.armed_state()
        if arming_state != existing_state:
            self.set_state(self.alarm_panel,state=arming_state)
            self.log('AUTOARM Setting %s from %s to %s' % (self.alarm_panel,existing_state,arming_state))
            return arming_state
        else:
            self.log('Skipping arm, as %s already %s' % (self.alarm_panel,arming_state))
            return existing_state

    def notify_flex(self,message,profile='normal',title=None):
        try:
            # separately merge base dict and data sub-dict as cheap and nasty semi-deep-merge
            selected_profile=self.notify_profiles.get(profile)
            base_profile=self.notify_profiles.get('common',{})
            base_profile_data=base_profile.get('data',{})
            selected_profile_data=selected_profile.get('data',{})
            merged_profile=dict(base_profile)
            merged_profile.update(selected_profile)
            merged_profile_data=dict(base_profile_data)
            merged_profile_data.update(selected_profile_data)
            merged_profile['data']=merged_profile_data

            title=title or 'Alarm Auto Arming'
            if merged_profile:
                self.notify(message,name=merged_profile['service'],
                                title=title,
                                data=merged_profile.get('data',{}))
        except Exception as e:
            self.error('AUTOARM %s failed %s' % ( self.notify_service, e))

    def on_sleep_start(self, kwargs):
        self.log('AUTOARM Sleep Period Start: %s' % kwargs)
        self.reset_at_home(hint_arming="armed_night")

    def on_reset_button(self, entity, attribute, old, new, kwargs):
        self.log('AUTOARM Reset Button: %s,%s,%s,%s,%s' % (entity, attribute, old, new, kwargs))
        self.last_request=time.time()
        self.reset_at_home()

    def on_mobile_action(self,event_name, data, cbargs):
        self.log('AUTOARM Mobile Action: %s,%s,%s' % (event_name, data, cbargs))
        self.last_request=time.time()
        match data.get('action'):
            case 'ALARM_PANEL_DISARM':
                self.arm("disarmed")
            case 'ALARM_PANEL_RESET':
                self.reset_at_home()
            case 'ALARM_PANEL_AWAY':
                self.arm("armed_away")
            case _:
                self.log('AUTOARM Ignoring mobile action: %s',data)

    def on_disarm_button(self, entity, attribute, old, new, kwargs):
        self.log('AUTOARM Disarm Button: %s,%s,%s,%s,%s' % (entity, attribute, old, new, kwargs))
        self.last_request=time.time()
        self.arm("disarmed")

    def on_vacation_button(self, entity, attribute, old, new, kwargs):
        self.log('AUTOARM Vacation Button: %s,%s,%s,%s,%s' % (entity, attribute, old, new, kwargs))
        self.last_request=time.time()
        self.arm("armed_vacation")

    def on_away_button(self, entity, attribute, old, new, kwargs):
        self.log('AUTOARM Away Button: %s,%s,%s,%s,%s' % (entity, attribute, old, new, kwargs))
        self.last_request=time.time()
        if self.arm_away_delay:
            self.run_in(self.delayed_arm,self.arm_away_delay,
                request_time=time.time(),arming_state="armed_away")
            self.notify_flex("Alarm will be armed for away in %s seconds" % self.arm_away_delay,
                                title="Arm for away process starting")
        else:
            self.arm("armed_away")

    def on_sleep_end(self, kwargs):
        self.log('AUTOARM Sleep Period End: %s' % kwargs)
        if self.is_occupied() and self.auto_disarm:
            self.arm("disarmed")
        else:
            self.reset_at_home(hint_arming="armed_home",force_arm=False)

    def on_sunrise(self, kwargs):
        self.log('AUTOARM Sunrise: %s' % kwargs)
        if not self.sunrise_cutoff or datetime.datetime.now().time() >= self.sunrise_cutoff:
            self.reset_at_home(hint_arming="armed_home",force_arm=False)
        elif self.sunrise_cutoff < self.sleep_end:
            sunrise_delay=total_secs(self.sleep_end)-total_secs(self.sunrise_cutoff)
            self.log('AUTOARM Rescheduling delayed sunrise action in %s seconds' % sunrise_delay)
            self.run_in(self.delayed_arm,sunrise_delay,reset=True,
                        requested_at=time.time(),arming_state='armed_home')

    def on_sunset(self, kwargs):
        self.log('AUTOARM Sunset: %s' % kwargs)
        self.reset_at_home(force_arm=False,hint_arming='armed_night')