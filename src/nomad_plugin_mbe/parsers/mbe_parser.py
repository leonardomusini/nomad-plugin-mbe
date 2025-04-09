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
from nomad.parsing import MatchingParser
from nomad.datamodel import EntryArchive
from nomad_plugin_mbe.schema_packages.mbe_schema import (
    SampleMBESynthesis, SampleRecipe, SubstrateDescription, User,
    SampleGrowingEnvironment, LayerDescription, SensorDescription,
    Instruments, CoolingDevice
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
            entry = hdf["entry"]

            # Extract general metadata
            growth_info.definition = hdf["entry/definition"][()].decode("utf-8") if "definition" in hdf["entry"] else None
            growth_info.title = hdf["entry/title"][()].decode("utf-8") if "title" in hdf["entry"] else None
            growth_info.growth_description = hdf["entry/experiment_description"][()].decode("utf-8") if "experiment_description" in hdf["entry"] else "No description provided"

            # Extract timestamps
            growth_info.start_time = parse_datetime(hdf["entry"], "start_time")
            growth_info.end_time = parse_datetime(hdf["entry"], "end_time")
            growth_info.duration = hdf["entry/duration"][()] if "duration" in hdf["entry"] else None

            # Extract user information
            for user_name in ["user", "user_1","user_2"]:
                if user_name in hdf["entry"]:
                    user_data = entry[user_name]
                    user = growth_info.m_create(User)

                    user.name = user_data["name"][()].decode("utf-8") if "name" in user_data else None
                    user.email = user_data["email"][()].decode("utf-8") if "email" in user_data else None
                    user.role = user_data["role"][()].decode("utf-8") if "role" in user_data else None
                    user.affiliation = user_data["affiliation"][()].decode("utf-8") if "affiliation" in user_data else None
                    user.ORCID = user_data["ORCID"][()].decode("utf-8") if "ORCID" in user_data else None

            # Extract apparatus information
            if "instrument" in hdf["entry"]:
                instrument_data = hdf["entry/instrument"]
                instrument = growth_info.m_create(Instruments)

                # Extract chamber information
                if "chamber" in hdf["entry/instrument"]:
                    chamber_data = hdf["entry/instrument/chamber"]
                    chamber = instrument.m_create(SampleGrowingEnvironment)

                    chamber.model = chamber_data["name"][()].decode("utf-8") if "name" in chamber_data else None
                    chamber.type = chamber_data["type"][()].decode("utf-8") if "type" in chamber_data else None
                    chamber.description = chamber_data["description"][()].decode("utf-8") if "description" in chamber_data else None

                    if "cooling_device" in instrument_data:
                        device_data = hdf["entry/instrument/cooling_device"]
                        device = chamber.m_create(CoolingDevice)

                        device.name = device_data["name"][()].decode("utf-8") if "name" in device_data else None
                        device.model = device_data["model"][()].decode("utf-8") if "model" in device_data else None
                        device.cooling_mode = device_data["cooling_mode"][()].decode("utf-8") if "cooling_mode" in device_data else None
                        device.temperature = device_data["temperature"][()] if "temperature" in device_data else None

                    # Extract sensors (pyrometers, reflectometers)
                    for sensor_name in ["sensor_1", "sensor_2", "sensor_3", "sensor_4", "sensor_5"]:
                        if sensor_name in chamber_data:
                            sensor_data = chamber_data[sensor_name]
                            sensor = chamber.m_create(SensorDescription)

                            sensor.name = sensor_data["name"][()].decode("utf-8") if "name" in sensor_data else None
                            sensor.model = sensor_data["model"][()].decode("utf-8") if "model" in sensor_data else None
                            sensor.measurement = sensor_data["measurement"][()].decode("utf-8") if "measurement" in sensor_data else None
                            if sensor.name == "Ion Gauge":
                                sensor.value = sensor_data["value"][()] if "value" in sensor_data else None

            # Extract sample recipe
            if "sample" in hdf["entry"]:
                sample_data = hdf["entry/sample"]
                sample = growth_info.m_create(SampleRecipe)

                sample.name = sample_data["name"][()].decode("utf-8") if "name" in sample_data else None
                sample.thickness = sample_data["thickness"][()] if "thickness" in sample_data else None

                # Extract substrate details
                if "substrate" in hdf["entry/sample"]:
                    substrate_data = hdf["entry/sample/substrate"]
                    substrate = sample.m_create(SubstrateDescription)

                    substrate.name = substrate_data["name"][()].decode("utf-8") if "name" in substrate_data else None
                    substrate.chemical_formula = substrate_data["chemical_formula"][()].decode("utf-8") if "chemical_formula" in substrate_data else None
                    substrate.crystalline_structure = substrate_data["crystalline_structure"][()].decode("utf-8") if "crystalline_structure" in substrate_data else None
                    substrate.crystal_orientation = substrate_data["crystal_orientation"][()].decode("utf-8") if "crystal_orientation" in substrate_data else None
                    substrate.doping = substrate_data["doping"][()].decode("utf-8") if "doping" in substrate_data else None
                    substrate.diameter = substrate_data["diameter"][()] if "diameter" in substrate_data else None
                    substrate.thickness = substrate_data["thickness"][()] if "thickness" in substrate_data else None
                    substrate.area = substrate_data["area"][()] if "area" in substrate_data else None
                    substrate.flat_convention = substrate_data["flat_convention"][()].decode("utf-8") if "flat_convention" in substrate_data else None
                    substrate.holder = substrate_data["holder"][()].decode("utf-8") if "holder" in substrate_data else None

                # Extract growth layers
                layer_index = 1
                while f"layer{layer_index:02d}" in sample_data:
                    layer_data = hdf[f"entry/sample/layer{layer_index:02d}"]
                    layer = sample.m_create(LayerDescription)

                    layer.name = layer_data["name"][()].decode("utf-8") if "name" in layer_data else None
                    layer.chemical_formula = layer_data["chemical_formula"][()].decode("utf-8") if "chemical_formula" in layer_data else None
                    layer.doping = layer_data["doping"][()].decode("utf-8") if "doping" in layer_data else None
                    layer.alloy_fraction = layer_data["alloy_fraction"][()] if "alloy_fraction" in layer_data else None
                    layer.thickness = layer_data["thickness"][()] if "thickness" in layer_data else None
                    layer.growth_temperature = layer_data["growth_temperature"][()] if "growth_temperature" in layer_data else None
                    layer.growth_time = layer_data["growth_time"][()] if "growth_time" in layer_data else None
                    layer.growth_rate = layer_data["growth_rate"][()] if "growth_rate" in layer_data else None
                    layer.rotational_frequency = layer_data["rotational_frequency"][()] if "rotational_frequency" in layer_data else None
                    layer.partial_pressure = layer_data["partial_pressure"][()] if "partial_pressure" in layer_data else None

                    # Partial growth rates
                    layer.partial_growth_rate_Ga1 = layer_data["partial_growth_rate_Ga1"][()] if "partial_growth_rate_Ga1" in layer_data else None
                    layer.partial_growth_rate_Ga2 = layer_data["partial_growth_rate_Ga2"][()] if "partial_growth_rate_Ga2" in layer_data else None
                    layer.partial_growth_rate_Al = layer_data["partial_growth_rate_Al"][()] if "partial_growth_rate_Al" in layer_data else None
                    layer.partial_growth_rate_In = layer_data["partial_growth_rate_In"][()] if "partial_growth_rate_In" in layer_data else None

                    layer_index += 1

            logger.info("HDF5 file successfully parsed into NOMAD schema.")