import numpy as np

from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, \
    comon_parameters, main
from pymodaq.utils.data import DataFromPlugins

import seabreeze
#seabreeze.use('cseabreeze')
from seabreeze.spectrometers import Spectrometer, list_devices

# Note: there's no special controller because that job is already done
# by the seabreeze library.

class DAQ_1DViewer_Oceanoptics(DAQ_Viewer_base):
    """ Instrument plugin class for a 1D viewer using Ocean Optics' seabreeze
        library.

    Tested for Ocean Optics USB2000 spectrometers.
    Should be compatible with other spectrometers which can be controlled
    with the seabreeze library.

    Attributes:
    -----------

    integrationtime
    """

    device_names = [str(device) for device in list_devices()]
    hardware_averaging = True

    params = comon_parameters+[
        { 'title': 'Device:', 'name': 'device_name', 'type': 'list',
          'limits': device_names },
        { 'title': 'Integration Time [ms]:', 'name': 'integration',
          'type': 'float', 'value': 1.0 },
        { 'title': 'X-Axis in wavenumbers:', 'name': 'wavenumber',
          'type': 'bool', 'value': False },
        ]

    def ini_attributes(self):
        self.controller: Spectrometer = None
        self.x_axis = None
        self.device_connected = False # see stop method

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been
            changed by the user
        """
        if param.name() == "integration":
            self.controller.integration_time_micros(param.value() * 1000)
        elif param.name() == "wavenumber":
            if self.x_axis is not None:
                pass # change self.x_axis

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one 
            actuator/detector by controller (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """

        self.ini_detector_init(slave_controller=controller)

        if self.is_master:
            device_name = self.settings.child('device_name').value()
            device_index = self.device_names.index(device_name)
            self.controller = Spectrometer(list_devices()[device_index])
            self.controller.open()
            self.device_connected = True

            self.first_used_pixel = \
                self.controller.f.spectrometer\
                                 .get_electric_dark_pixel_indices()[-1]
            wavelengths = self.controller.wavelengths()[self.first_used_pixel:]
            self.x_axis = Axis(label='Wavelength', units='nm',
                                data=wavelengths, index=0)
            dfp = DataFromPlugins(name='Avantes',
                                  data=[np.zeros(len(wavelengths))],
                                  dim='Data1D', axes=[self.x_axis],
                                  labels=['Intensities'])
            self.dte_signal_temp.emit(DataToExport(name='Avantes', data=[dfp]))
            tlimits = \
                np.array(self.controller.integration_time_micros_limits) / 1000
            self.settings.child('integration').setLimits(tlimits)
            self.controller.close()
            self.device_connected = False

        info = "OcenaOptics Spectrometer initilialized"
        initialized = True

        return info, initialized

    def close(self):
        """Terminate the communication protocol"""
        self.controller.close()
        self.device_connected = False
        self.x_axis = None

    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Number of hardware averaging (if hardware averaging is possible, 
            self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        if not self.device_connected: # see stop method
            self.controller.open()
            self.device_connected = True

        if Naverage > 1:
            raw_data = [self.controller.intensities()[self.first_used_pixel:] \
                        for i in range(Naverage)]
            data = np.array(raw_data).mean(0)
        else:
            data = self.controller.intensities()[self.first_used_pixel:]

        dfp = DataFromPlugins(name='seabreeze', data=[data], dim='Data1D',
                              labels=['Intensity'], axis=[self.x_axis])

        self.dte_signal.emit(DataToExport(name='intensities', data=[dfp]))

    def callback(self):
        pass

    def stop(self):
        # bugfix, when operating from this script only,
        # the close methods of the plugin is never called, leaving the
        # seabreeze library in a dead state. Only unplugging and replugging
        # the device gets it back to life. So we close communication here
        # in case the plugin is shut down afer this call.
        self.controller.close()
        self.device_connected = False


if __name__ == '__main__':
    main(__file__)
