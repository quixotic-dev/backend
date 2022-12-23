from time import sleep

from solcx import compile_source, install_solc, set_solc_version

from .launchpad_libraries import launchpad_libraries
from .solidity_contract_creation_helpers import write_smart_contract_src_code


def create_flattened_solidity(init):
    launchpad_src = write_smart_contract_src_code(init)
    return launchpad_libraries + launchpad_src


def create_launchpad_contract(init, retries=5):
    install_solc("0.8.7")
    set_solc_version("0.8.7")
    src = create_flattened_solidity(init)
    compiled_sol = compile_source(src, output_values=["abi", "bin"])
    contract_id = "<stdin>:QuixoticLaunchpadERC721"
    contract_interface = compiled_sol.get(contract_id)
    abi = contract_interface["abi"]
    bytecode = contract_interface["bin"]
    return abi, bytecode, src

    try:
        set_solc_version("0.8.7")
        src = create_flattened_solidity(init)
        compiled_sol = compile_source(src, output_values=["abi", "bin"])
        contract_id = "<stdin>:QuixoticLaunchpadERC721"
        contract_interface = compiled_sol.get(contract_id)
        abi = contract_interface["abi"]
        bytecode = contract_interface["bin"]
        return abi, bytecode, src
    except Exception as e:
        print(e)
        install_solc("0.8.7")
        if retries > 0:
            sleep(5)
            return create_launchpad_contract(init, retries - 1)
        else:
            raise Exception(f"Ran out of retries for exception: {e}")
