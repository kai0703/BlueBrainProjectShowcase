"""Script to parse models download from NMC portal and convert to NML2"""

# pylint: disable=F0401, C0325, W0603, R0914, R0912, W0602

import os
import sys
from pyneuroml.neuron import export_to_neuroml2
from pyneuroml.neuron.nrn_export_utils import clear_neuron

from pyneuroml.lems import generate_lems_file_for_neuroml

from pyneuroml import pynml
import neuroml

import shutil

import zipfile

from Biophysics import get_biophysical_properties

from jinja2 import Template

# from neuroml import *
# from neuron import *
# from nrn import *
import json
import os.path


groups_info_file = 'groups.txt'
iclamp_info_file = 'current_amps.dat'


def get_stimulus_amplitudes(bbp_ref):
    """Get stimulus amplitudes"""

    hyp = ''
    dep = ''
    for line in open(iclamp_info_file):
        words = line.split(' ')
        hyp = '%snA' % words[0]
        dep = '%snA' % words[3]
    return hyp, dep


def parse_cell_info_file(cell_dir):
    """Parse cell info file"""

    cell_info_json = 'cellinfo.json'
    if os.path.isfile(cell_info_json):
        print("Reading cell info from: %s" % os.path.abspath(cell_info_json))
        with open(cell_info_json) as data_file:
            data = json.load(data_file)

            return data

    else:
        data = {}
        e_type = ''
        e_type_info = cell_dir.split('_')[2]
        for c in e_type_info:
            if not c.isdigit():
                e_type += c
        data['e-type'] = e_type

        return data

zips_dir = '../zips'
make_zips = '-zip' in sys.argv
nml2_cell_dir = '../../NeuroML2/'

cell_dirs = []
net_doc = None
net = None


def main():
    """Main"""

    global cell_dirs, nml2_cell_dir, net, net_doc

    net_ref = "ManyCells"
    net_doc = neuroml.NeuroMLDocument(id=net_ref)

    net = neuroml.Network(id=net_ref)
    net_doc.networks.append(net)

    cell_dirs = [
        f
        for f in os.listdir
        ('.')
        if(os.path.isdir(f) and os.path.isfile(f + '/.provenance.json'))]

    clear_neuron()

    map(process_celldir, enumerate(cell_dirs))

    count = len(cell_dirs)
    if not make_zips:
        net_file = '%s/%s.net.nml' % (nml2_cell_dir, net_ref)
        neuroml.writers.NeuroMLWriter.write(net_doc, net_file)

        print(
            "Written network with %i cells in network to: %s" %
            (count, net_file))

        pynml.nml2_to_svg(net_file)


def process_celldir(count_cell_dir):
    """Process cell directory"""

    global cell_dirs, nml2_cell_dir, net_doc, net

    count, cell_dir = count_cell_dir

    print(
        '\n\n************************************************************\n\n'
        'Parsing %s (cell %i/%i)\n' %
        (cell_dir, count, len(cell_dirs)))

    if os.path.isdir(cell_dir):
        os.chdir(cell_dir)
    else:
        os.chdir('../' + cell_dir)

    if make_zips:
        nml2_cell_dir = '%s/%s' % (zips_dir, cell_dir)
        if not os.path.isdir(nml2_cell_dir):
            os.mkdir(nml2_cell_dir)

    print("Generating into %s" % nml2_cell_dir)

    bbp_ref = None

    template_file = open('template.hoc', 'r')
    for line in template_file:
        if line.startswith('begintemplate '):
            bbp_ref = line.split(' ')[1].strip()
            print(
                ' > Assuming cell in directory %s is in a template named %s' %
                (cell_dir, bbp_ref))

    load_cell_file = 'loadcell.hoc'

    variables = {}

    variables['cell'] = bbp_ref
    variables['groups_info_file'] = groups_info_file

    template = """
///////////////////////////////////////////////////////////////////////////////
//
//   NOTE: This file is not part of the original BBP cell model distribution
//   It has been generated by ../ParseAll.py to facilitate loading of the cell
//   into NEURON for exporting the model morphology to NeuroML2
//
//////////////////////////////////////////////////////////////////////////////

load_file("nrngui.hoc")

objref cvode
cvode = new CVode()
cvode.active(1)

//======================== settings ===================================

v_init = -80

hyp_amp = -0.062866
step_amp = 0.3112968
tstop = 3000

//=================== creating cell object ===========================
load_file("import3d.hoc")
objref cell

// Using 1 to force loading of the file, in case file with same name was loaded
// before...
load_file(1, "constants.hoc")
load_file(1, "morphology.hoc")
load_file(1, "biophysics.hoc")
print "Loaded morphology and biophysics..."

load_file(1, "synapses/synapses.hoc")
load_file(1, "template.hoc")
print "Loaded template..."

load_file(1, "createsimulation.hoc")


create_cell(0)
print "Created new cell using loadcell.hoc: {{ cell }}"

define_shape()

wopen("{{ groups_info_file }}")

fprint("//Saving information on groups in this cell...\\n")

fprint("- somatic\\n")
forsec {{ cell }}[0].somatic {
    fprint("%s\\n",secname())
}

fprint("- basal\\n")
forsec {{ cell }}[0].basal {
    fprint("%s\\n",secname())
}

fprint("- axonal\\n")
forsec {{ cell }}[0].axonal {
    fprint("%s\\n",secname())
}
fprint("- apical\\n")
forsec {{ cell }}[0].apical {
    fprint("%s\\n",secname())
}
wopen()
        """

    t = Template(template)

    contents = t.render(variables)

    load_cell = open(load_cell_file, 'w')
    load_cell.write(contents)
    load_cell.close()

    print(' > Written %s' % load_cell_file)

    if os.path.isfile(load_cell_file):

        cell_info = parse_cell_info_file(cell_dir)

        nml_file_name = "%s.net.nml" % bbp_ref
        nml_net_loc = "%s/%s" % (nml2_cell_dir, nml_file_name)
        nml_cell_file = "%s_0_0.cell.nml" % bbp_ref
        nml_cell_loc = "%s/%s" % (nml2_cell_dir, nml_cell_file)

        print(
            ' > Loading %s and exporting to %s' %
            (load_cell_file, nml_net_loc))

        export_to_neuroml2(load_cell_file,
                           nml_net_loc,
                           separateCellFiles=True,
                           includeBiophysicalProperties=False)

        print(
            ' > Exported to: %s and %s using %s' %
            (nml_net_loc, nml_cell_loc, load_cell_file))

        nml_doc = pynml.read_neuroml2_file(nml_cell_loc)

        cell = nml_doc.cells[0]

        print(' > Adding groups from: %s' % groups_info_file)
        groups = {}
        current_group = None
        for line in open(groups_info_file):
            if not line.startswith('//'):
                if line.startswith('- '):
                    current_group = line[2:-1]
                    print(' > Adding group: [%s]' % current_group)
                    groups[current_group] = []
                else:
                    section = line.split('.')[1].strip()
                    segment_group = section.replace('[', '_').replace(']', '')
                    groups[current_group].append(segment_group)

        for g in groups.keys():
            new_seg_group = neuroml.SegmentGroup(id=g)
            cell.morphology.segment_groups.append(new_seg_group)
            for sg in groups[g]:
                new_seg_group.includes.append(neuroml.Include(sg))
            if g in ['basal', 'apical']:
                new_seg_group.inhomogeneous_parameters.append(
                    neuroml.InhomogeneousParameter(
                        id="PathLengthOver_" + g,
                        variable="p",
                        metric="Path Length from root",
                        proximal=neuroml.ProximalDetails(
                            translation_start="0")))

        ignore_chans = ['Ih', 'Ca_HVA', 'Ca_LVAst', 'Ca',
                        "SKv3_1", "SK_E2", "CaDynamics_E2", "Nap_Et2", "Im",
                        "K_Tst", "NaTa_t", "K_Pst", "NaTs2_t"]

        # ignore_chans=['StochKv','StochKv_deterministic']
        ignore_chans = []

        bp, incl_chans = get_biophysical_properties(
            cell_info['e-type'], ignore_chans=ignore_chans,
            templates_json="../templates.json")

        cell.biophysical_properties = bp

        print("Set biophysical properties")

        notes = ''
        notes += \
            "\n\nExport of a cell model obtained from the BBP Neocortical" \
            "Microcircuit Collaboration Portal into NeuroML2" \
            "\n\n******************************************************\n*" \
            "  This export to NeuroML2 has not yet been fully validated!!" \
            "\n*  Use with caution!!\n***********************************" \
            "*******************\n\n"

        if len(ignore_chans) > 0:
            notes += "Ignored channels = %s\n\n" % ignore_chans

        notes += "For more information on this cell model see: " \
            "https://bbp.epfl.ch/nmc-portal/microcircuit#/metype/%s/" \
            "details\n\n" % cell_info['me-type']

        cell.notes = notes
        for channel in incl_chans:

            nml_doc.includes.append(neuroml.IncludeType(
                href="%s" % channel))

            if make_zips:
                print("Copying %s to zip folder" % channel)
                shutil.copyfile(
                    '../../NeuroML2/%s' %
                    channel, '%s/%s' %
                    (nml2_cell_dir, channel))

        pynml.write_neuroml2_file(nml_doc, nml_cell_loc)

        stim_ref = 'stepcurrent3'
        stim_ref_hyp = '%s_hyp' % stim_ref
        stim_sim_duration = 3000
        stim_hyp_amp, stim_amp = get_stimulus_amplitudes(bbp_ref)
        stim_del = '700ms'
        stim_dur = '2000ms'

        new_net_loc = "%s/%s.%s.net.nml" % (nml2_cell_dir, bbp_ref, stim_ref)
        new_net_doc = pynml.read_neuroml2_file(nml_net_loc)

        new_net_doc.notes = notes

        stim_hyp = neuroml.PulseGenerator(
            id=stim_ref_hyp,
            delay="0ms",
            duration="%sms" %
            stim_sim_duration,
            amplitude=stim_hyp_amp)
        new_net_doc.pulse_generators.append(stim_hyp)
        stim = neuroml.PulseGenerator(
            id=stim_ref,
            delay=stim_del,
            duration=stim_dur,
            amplitude=stim_amp)
        new_net_doc.pulse_generators.append(stim)

        new_net = new_net_doc.networks[0]

        pop_id = new_net.populations[0].id
        pop_comp = new_net.populations[0].component
        input_list = neuroml.InputList(id="%s_input" % stim_ref_hyp,
                                       component=stim_ref_hyp,
                                       populations=pop_id)

        syn_input = neuroml.Input(id=0,
                                  target="../%s/0/%s" % (pop_id, pop_comp),
                                  destination="synapses")

        input_list.input.append(syn_input)
        new_net.input_lists.append(input_list)

        input_list = neuroml.InputList(id="%s_input" % stim_ref,
                                       component=stim_ref,
                                       populations=pop_id)

        syn_input = neuroml.Input(id=0,
                                  target="../%s/0/%s" % (pop_id, pop_comp),
                                  destination="synapses")

        input_list.input.append(syn_input)
        new_net.input_lists.append(input_list)

        pynml.write_neuroml2_file(new_net_doc, new_net_loc)

        generate_lems_file_for_neuroml(cell_dir,
                                       new_net_loc,
                                       "network",
                                       stim_sim_duration,
                                       0.025,
                                       "LEMS_%s.xml" % cell_dir,
                                       nml2_cell_dir,
                                       copy_neuroml=False,
                                       seed=1234)

        pynml.nml2_to_svg(nml_net_loc)

        clear_neuron()

        net_doc.includes.append(neuroml.IncludeType(nml_cell_file))

        pop = neuroml.Population(
            id="Pop_%s" %
            bbp_ref,
            component=bbp_ref +
            '_0_0',
            type="populationList")

        net.populations.append(pop)

        inst = neuroml.Instance(id="0")
        pop.instances.append(inst)

        width = 6
        X = count % width
        Z = (count - X) / width
        inst.location = neuroml.Location(x=300 * X, y=0, z=300 * Z)

        count += 1

        if make_zips:
            zip_file = "%s/%s.zip" % (zips_dir, cell_dir)
            print("Creating zip file: %s" % zip_file)
            with zipfile.ZipFile(zip_file, 'w') as myzip:

                for next_file in os.listdir(nml2_cell_dir):
                    next_file = '%s/%s' % (nml2_cell_dir, next_file)
                    arcname = next_file[len(zips_dir):]
                    print("Adding : %s as %s" % (next_file, arcname))
                    myzip.write(next_file, arcname)


if __name__ == '__main__':
    main()
