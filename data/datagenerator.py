# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from datetime import date
from datetime import timedelta
from pathlib import Path

import click
import pandas as pd
import numpy as np
from scipy.stats import poisson


# %%
@dataclass
class Department:
    """ Define the properties of a department"""
    name: str
    employees: float
    intracomm: float
    intercomm: float
    friendscomm: float

@dataclass
class Channel:
    """ Define baseline properties of different communication media """
    name: str
    freq: int

@dataclass
class Employee:
    """ Communication behavior of employee"""
    idx: int
    department: str
    remote: bool
    fulltime: bool
    communicative: float
    channel_baseline: List[int]
    intracomm: float
    intercomm: float
    friendscomm: float
    friends: List[int]
    hasCommunicationIssues: bool

@dataclass
class Communication:
    """ Defines a single communication (row in the communication graph) """
    sender: int
    recver: int
    channel: str
    interactions: int
    date: str

def generate_behavior(cfg: Dict, seed: Optional[int] = None, permutation_rate: float = 0.1) -> Tuple[Dict, Dict]:
    """
    For given configuration generate preferences and behavior for each employee
    """
    np.random.seed(seed)
    stats = {}
    stats['employees_per_department'] = [int(dep.employees * cfg['employees']) for dep in cfg['departments'].values()]

    # Number of employees per department
    stats['department_per_employee'] = []
    _ = [stats['department_per_employee'].extend([dep.name,] * cnt) for cnt, dep in zip(stats['employees_per_department'], cfg['departments'].values())]

    # Select a number of other employees as friends (frequent communication patners)
    # Let it be a normal distribution around 5, with a standard deviation of 2 and a minimal value of 1
    total_employee_cnt = sum(stats['employees_per_department'])
    employee_friends = [np.random.choice(range(total_employee_cnt), size=max(1, int(nfriends))) for nfriends in np.round(np.random.normal(loc=5, scale=2, size=total_employee_cnt), decimals=0)]
        
    stats['remote'] = [True if p < cfg['ratio_of_remote_employees'] else False for p in np.random.uniform(low=0.0, high=1.0, size=total_employee_cnt)]
    stats['fulltime'] = [True if p < cfg['ratio_of_fulltime_employees'] else False for p in np.random.uniform(low=0.0, high=1.0, size=total_employee_cnt)]    

    # min_comm_behavior = 0.1
    stats['base_comm_behavior'] = [max(1, int(x)) for x in np.random.normal(loc=10, scale=3, size=total_employee_cnt)]

    # A dictionary of employee_idx per department (employeeidx starts at 1000)
    stats['departmentlist'] = {dep_name: [] for dep_name in cfg['departments'].keys()}

    stats['hasCommunicationIssues'] = np.random.choice([True, False], p=[permutation_rate, 1.0 - permutation_rate], size=total_employee_cnt)

    # Build a dictionary of employees, indexed by their idx
    employees = {}
    for i, (department, base_comm, remote, fulltime, friends, hasCI) in enumerate(
        zip(stats['department_per_employee'], stats['base_comm_behavior'], stats['remote'], stats['fulltime'], employee_friends, stats['hasCommunicationIssues'])):
        
        # employee idx starts
        idx=i

        # If not working fulltime, reduce comm
        if fulltime:
            worktime = 1.0
        else:
            worktime = 0.5
        
        # Remote workers comm a bit more
        if remote:
            remotetime = 1.5
        else:
            remotetime = 1.0

        # define how many different interactions (i.e. node degree) a employee has per day
        communicative = int(base_comm*worktime*remotetime)

        # Simple perturbation. This employee will have very few interactions
        if hasCI:
            communicative = 3

        # define the intensity of those interactions per channel
        # media.freq * employee_communication_tendency * media_bias
        channel_comm_freq = [cfg['channels'][m].freq*media_bias
            for m, media_bias in zip(cfg['channels'], np.random.uniform(low=0.5, high=1.5, size=len(cfg['channels'])))]
        channel_comm_freq = np.int_(np.round(channel_comm_freq, decimals=0))

        intracomm = cfg['departments'][department].intracomm * float(np.random.uniform(low=0.5, high=1.5, size=1))
        intercomm = cfg['departments'][department].intercomm * float(np.random.uniform(low=0.5, high=1.5, size=1))
        friendscomm = cfg['departments'][department].friendscomm * float(np.random.uniform(low=0.5, high=1.5, size=1))
        comm_summ = intracomm + intercomm + friendscomm
        intracomm *= 1.0/comm_summ
        intercomm *= 1.0/comm_summ
        friendscomm *= 1.0/comm_summ

        employees[idx]=Employee(idx=idx,
        department=department,
        remote=remote,
        fulltime=fulltime,
        communicative=communicative,
        channel_baseline=channel_comm_freq,
        intracomm = intracomm,
        intercomm = intercomm,
        friendscomm = friendscomm,
        friends=friends,
        hasCommunicationIssues=hasCI)

        stats['departmentlist'][department].append(idx)
    
    return stats['departmentlist'], employees

def _getIdx(employee: Employee, groups: List[int], departmentlist: Dict[str, int]) -> List[int]:
    """
    For given employee and groups (department, other department, friends) return matching employee idx
    """
    idxs = []
    all_employees = []
    _ = [all_employees.extend(x) for x in departmentlist.values()]

    for group in groups:
        if group == 0:
            # same department
            idx = np.random.choice(departmentlist[employee.department])
        elif group == 1:
            # Other departments
            idx = np.random.choice(all_employees)
        elif group == 2:
            # Friends
            idx = np.random.choice(employee.friends)
        else:
            raise Exception('Invalid group id')
    
        idxs.append(idx)
    return idxs


def get_communication_for_employee(employee: Employee, date: str, departmentlist: Dict[str, int], channels: List[str]) -> List[Communication]:
    """
    For given employee create all communication events for given day
    """
    degree = np.random.poisson(employee.communicative)
    groups = np.random.choice([0, 1, 2], p=[employee.intracomm, employee.intercomm, employee.friendscomm], size=degree)
    dests = _getIdx(employee, groups, departmentlist)
    chls = np.random.choice(range(len(channels)), size=degree)
    channel_names = [channels[x] for x in chls]
    intensities = [np.random.poisson(employee.channel_baseline[channel]) for channel in chls]

    comms = []
    for dest, channel, intensity in zip(dests, channel_names, intensities):
        comms.append(
            Communication(
                sender=employee.idx,
                recver=dest,
                channel=channel,
                interactions=intensity,
                date=date
            )
        )
 
    return comms

def store_results(path: str, comms: List[Communication], employees: List[Employee], prefix: Optional[str] = ''):
    """
    Store communication and employees as csv files
    """
    commpath = Path(path).joinpath(prefix+'communication.csv')
    employeepath = Path(path).joinpath(prefix+'employees.csv')
    commDF = pd.DataFrame(comms)
    employeeDF = pd.DataFrame(employees)
    employeeDF = employeeDF[['idx', 'department', 'remote', 'fulltime', 'hasCommunicationIssues']]

    print(f'Writing communication data to {commpath} ...')
    commDF.to_csv(commpath, index=False)

    print(f'Writing employee data to {employeepath} ...')
    employeeDF.to_csv(employeepath, index=False)



def _generate_dataset(cfg, output_path, seed, nDays=10, permutation_rate=0.1):
    # %%
    departmentlist, employees = generate_behavior(cfg, seed=seed, permutation_rate=permutation_rate)

    # %%
    np.random.seed(seed)
    comms = []
    for day in [date(2020, 1, 1) + timedelta(days=d) for d in range(nDays)]:
        print(f'Calculate for date {day} ... ')
        _ = [comms.extend(get_communication_for_employee(employee, day.isoformat(), departmentlist, list(cfg['channels'].keys()))) for employee in employees.values()]
    print(f'Produced {len(comms)} communication entries ...')
    
    # %%
    store_results(output_path.parent, comms, employees.values(), prefix=output_path.name)


@click.command()
@click.argument('N', type=click.INT)
@click.argument('outputprefix', type=click.Path(exists=False))
@click.option('--seed', default=42, help='Seed value')
@click.option('--permutation', default=0.1, help='Ratio of permuted employees')
@click.option('--days', default=10, help='Number of days to simulate')
def generate(n, outputprefix, seed, permutation, days):
    # %%
    cfg = {}
    # Number of nodes
    cfg['employees'] = n 

    cfg['departments'] = {
        'Business': Department("Business", 0.1, 0.3, 0.3, 0.3),
        'Administration': Department("Administration", 0.1, 0.3, 0.3, 0.3),
        'Sales': Department("Sales", 0.1, 0.4, 0.3, 0.3),
        'Marketing': Department("Marketing", 0.1, 0.5, 0.3, 0.2),
        'Research': Department("Research", 0.2, 0.6, 0.2, 0.2),
        'DevFrontend': Department("DevFrontend", 0.2, 0.5, 0.3, 0.2),
        'DevBackend': Department("DevBackend", 0.2, 0.5, 0.3, 0.2),
    }

    cfg['channels'] = {
        'slack': Channel('slack', 10),
        'zoom': Channel('zoom', 2),
        'email': Channel('email', 3),
    }

    cfg['ratio_of_fulltime_employees'] = 0.7
    cfg['ratio_of_remote_employees'] = 0.3

    p = Path(outputprefix).absolute()
    _generate_dataset(cfg, p, seed, nDays=days, permutation_rate=permutation)
    pass

################################################################################

if __name__ == '__main__':
    generate()