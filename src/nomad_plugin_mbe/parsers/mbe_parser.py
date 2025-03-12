from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from nomad.datamodel.datamodel import (
        EntryArchive,
    )
    from structlog.stdlib import (
        BoundLogger,
    )

from nomad.datamodel.datamodel import (
        EntryArchive,
    )
from structlog.stdlib import (
        BoundLogger,
    )

import h5py
from datetime import datetime
import numpy as np
from nomad.parsing import MatchingParser
from nomad.datamodel import EntryArchive
from nomad_plugin_mbe.schema_packages.mbe_schema import (
    SampleMBESynthesis, SampleReceipt, SubstrateDescription, User,
    SampleGrowingEnvironment, LayerStepDescription, GaugeDescription, SensorDescription
)


def parse_datetime(hdf5_obj, key):
    """Extracts and converts a datetime string from HDF5 to a Python datetime object."""
    if key in hdf5_obj:
        value = hdf5_obj[key][()]
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class HDF5MBEParser(MatchingParser):

    def __init__(self):
        super().__init__(
            name='HDF5MBEParser',
            code_name='MyHDF5MBECode',
            mainfile_name_re=r'.+\.nxs',
            mainfile_mime_re=r'application/x-hdf5'
        )

    def parse(self, mainfile: str, archive: EntryArchive, logger) -> None:
        """Parses the HDF5/NeXus file and maps it to the NOMAD data schema."""

        with h5py.File(mainfile, "r") as hdf:
            logger.info(f"Parsing HDF5 file: {mainfile}")

            # Create main metadata structure
            archive.data = SampleMBESynthesis()
            growth_info = archive.data

            # Extract general metadata
            growth_info.definition = hdf["entry/definition"][()].decode("utf-8") if "definition" in hdf["entry"] else None
            growth_info.title = hdf["entry/title"][()].decode("utf-8") if "title" in hdf["entry"] else "Unknown Growth Title"
            growth_info.growth_description = hdf["entry/experiment_description"][()].decode("utf-8") if "experiment_description" in hdf["entry"] else "No description provided"

            # Extract timestamps
            growth_info.start_time = parse_datetime(hdf["entry"], "start_time")
            growth_info.end_time = parse_datetime(hdf["entry"], "end_time")
            growth_info.duration = hdf["entry/duration"][()] if "duration" in hdf["entry"] else None

            # Extract user information
            if "user" in hdf["entry"]:
                user_data = hdf["entry/user"]
                user = growth_info.m_create(User)
                user.name = user_data["name"][()].decode("utf-8") if "name" in user_data else None
                user.role = user_data["role"][()].decode("utf-8") if "role" in user_data else None
                user.affiliation = user_data["affiliation"][()].decode("utf-8") if "affiliation" in user_data else None
                user.ORCID = user_data["ORCID"][()].decode("utf-8") if "ORCID" in user_data else None

            # Extract substrate details
            if "substrate" in hdf["entry"]:
                substrate_data = hdf["entry/substrate"]
                substrate = growth_info.m_create(SubstrateDescription)

                substrate.name = substrate_data["name"][()].decode("utf-8") if "name" in substrate_data else None
                substrate.chemical_formula = substrate_data["chemical_formula"][()].decode("utf-8") if "chemical_formula" in substrate_data else None
                substrate.crystallinity = substrate_data["cristallinity"][()].decode("utf-8") if "cristallinity" in substrate_data else None
                substrate.orientation = substrate_data["sample_orientation"][()].decode("utf-8") if "sample_orientation" in substrate_data else None
                substrate.doping = substrate_data["doping"][()].decode("utf-8") if "doping" in substrate_data else None
                substrate.diameter = substrate_data["diameter"][()] if "diameter" in substrate_data else None
                substrate.thickness = substrate_data["thickness"][()] if "thickness" in substrate_data else None
                substrate.area = substrate_data["area"][()] if "area" in substrate_data else None
                substrate.flat_convention = substrate_data["flat_convention"][()].decode("utf-8") if "flat_convention" in substrate_data else None
                substrate.holder = substrate_data["holder"][()].decode("utf-8") if "holder" in substrate_data else None

            # Extract sample receipt
            if "sample" in hdf["entry"]:
                sample_data = hdf["entry/sample"]
                sample = growth_info.m_create(SampleReceipt)

                sample.name = sample_data["name"][()].decode("utf-8") if "name" in sample_data else None
                sample.thickness = sample_data["thickness"][()] if "thickness" in sample_data else None

                # Extract chamber information
                if "chamber" in sample_data:
                    chamber_data = sample_data["chamber"]
                    chamber = sample.m_create(SampleGrowingEnvironment)

                    chamber.model = chamber_data["name"][()].decode("utf-8") if "name" in chamber_data else None
                    chamber.type = chamber_data["type"][()].decode("utf-8") if "type" in chamber_data else None
                    chamber.description = chamber_data["description"][()].decode("utf-8") if "description" in chamber_data else None

                    # Extract gauges
                    if "ion_gauge" in chamber_data:
                        gauge_data = chamber_data["ion_gauge"]
                        gauge = chamber.m_create(GaugeDescription)
                        gauge.model = gauge_data["name"][()].decode("utf-8") if "name" in gauge_data else None
                        gauge.measurement = gauge_data["measurement"][()].decode("utf-8") if "measurement" in gauge_data else None
                        gauge.value = gauge_data["value"][()] if "value" in gauge_data else None

                    # Extract sensors (pyrometers, reflectometers)
                    for sensor_name in ["pyrometer_1", "pyrometer_2", "reflectometer_1", "reflectometer_2"]:
                        if sensor_name in chamber_data:
                            sensor_data = chamber_data[sensor_name]
                            sensor = chamber.m_create(SensorDescription)

                            sensor.model = sensor_data["name"][()].decode("utf-8") if "name" in sensor_data else None
                            sensor.measurement = sensor_data["measurement"][()].decode("utf-8") if "measurement" in sensor_data else None
                            #sensor.wavelength = sensor_data["wavelength"][()].decode("utf-8") if "wavelength" in sensor_data else None

            # Extract growth layers
            layer_index = 1
            while f"layer{layer_index}" in hdf["entry/sample"]:
                layer_data = hdf[f"entry/sample/layer{layer_index}"]
                layer = sample.m_create(LayerStepDescription)

                layer.chemical_formula = layer_data["chemical_formula"][()].decode("utf-8") if "chemical_formula" in layer_data else None
                layer.alloy_fraction = layer_data["alloy_fraction"][()] if "alloy_fraction" in layer_data else None
                layer.thickness = layer_data["thickness"][()] if "thickness" in layer_data else None
                layer.growth_temperature = layer_data["growth_temperature"][()] if "growth_temperature" in layer_data else None
                layer.growth_time = layer_data["growth_time"][()] if "growth_time" in layer_data else None
                layer.growth_rate = layer_data["growth_rate"][()] if "growth_rate" in layer_data else None
                layer.rotation_velocity = layer_data["rotation_velocity"][()] if "rotation_velocity" in layer_data else None
                layer.partial_pressure = layer_data["partial_pressure"][()] if "partial_pressure" in layer_data else None

                # Evaporation rates
                layer.evaporation_rate_Ga1 = layer_data["evap_rate_Ga1"][()] if "evap_rate_Ga1" in layer_data else None
                layer.evaporation_rate_Ga2 = layer_data["evap_rate_Ga2"][()] if "evap_rate_Ga2" in layer_data else None
                layer.evaporation_rate_Al = layer_data["evap_rate_Al"][()] if "evap_rate_Al" in layer_data else None
                layer.evaporation_rate_In = layer_data["evap_rate_In"][()] if "evap_rate_In" in layer_data else None

                layer_index += 1

            logger.info("HDF5 file successfully parsed into NOMAD schema.")