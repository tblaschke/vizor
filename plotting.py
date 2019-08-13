import numpy as np
import os
import pandas as pd
from bokeh.layouts import column, row
from bokeh.layouts import layout
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.models.widgets import Div
from bokeh.models.widgets import Slider, DataTable, TableColumn, HTMLTemplateFormatter
from bokeh.plotting import figure
from bokeh.themes import Theme
from rdkit import Chem
from rdkit import rdBase
from rdkit.Chem import Draw
from rdkit.Chem import PandasTools

import logparser

rdBase.DisableLog('rdApp.error')


def get_position(data, pos):
    if pos < 0:
        return len(data) - pos
    else:
        return pos


def render_vizard(doc):
    args = doc.session_context.request.arguments
    req_path = args["req_path"][0].decode('utf-8')

    data = logparser.read_output_log(req_path)
    hover = create_hover_tool()

    score_plot, score_source = create_score_chart(data, title="Scores", x_name="Step", y_name="Average Score",
                                                  text_font_size="20pt")

    molecule_plot = create_2d_molecule(data, position=-1)
    slider = Slider(start=-1, end=len(data) - 1, value=-1, step=1, title="Step")

    template = """<span data-toggle="tooltip" title="<%= value %>"><%= svg %></span>"""
    columns = [
        TableColumn(field="Step", title="Step"),
        TableColumn(field="Score", title="Score"),
        TableColumn(field="SMILES", title="SMILES", formatter=HTMLTemplateFormatter(template=template)),
    ]
    smiles, score = extract_compounds(data, -1)
    molsvg = [create_hover_svg(smi) for smi in smiles]
    tabledf = dict(Step=[get_position(data, -1)] * len(smiles), SMILES=smiles, Score=score, svg=molsvg)
    table_source = ColumnDataSource(data=tabledf)
    data_table = DataTable(source=table_source, columns=columns, width=900, height=400)

    def slider_callback(attr, old, new):
        new = int(new)
        data = score_source.data["raw_data"]
        new_molecule_plot = create_2d_molecule(data, position=new)
        molecule_plot.text = new_molecule_plot.text
        smiles, score = extract_compounds(data, new)
        molsvg = [create_hover_svg(smi) for smi in smiles]
        tabledf = dict(Step=[get_position(data, new)] * len(smiles), SMILES=smiles, Score=score, svg=molsvg)
        table_source.data = tabledf

    def redraw_new_sliderend(attr, old, new):
        if slider.value == -1:
            slider_callback(attr, -1, -1)

    slider.on_change('value', slider_callback)
    slider.on_change('end', redraw_new_sliderend)

    bokehlayout = layout([row(column(molecule_plot, slider), score_plot), ], sizing_mode="fixed")
    doc.add_root(bokehlayout)

    def check_new_data():
        newdata = logparser.read_output_log(req_path)
        if len(newdata) > len(score_source.data["raw_data"]):
            x, y = extract_average_scores(newdata)
            y_mean = running_average(y, 50)
            score_source.data.update(x=x.tolist(), y=y.tolist(), y_mean=y_mean.tolist(), raw_data=newdata)
            slider.end = len(x) - 1

    doc.add_periodic_callback(check_new_data, 1000)
    doc.theme = Theme(filename=os.path.dirname(os.path.realpath(__file__)) + "/templates/theme.yaml")


def create_hover_tool():
    return None


def running_average(data, length):
    early_cumsum = np.cumsum(data[:length]) / np.arange(1, min(len(data), length) + 1)
    if len(data) > length:
        cumsum = np.cumsum(data)
        cumsum = (cumsum[length:] - cumsum[:-length]) / length
        cumsum = np.concatenate((early_cumsum, cumsum))
        return cumsum
    return early_cumsum


def extract_average_scores(data):
    steps = []
    scores = []
    for item in data:
        steps.append(item["Step"])
        if item["Score"] is None:
            avg_score = 0
            for smi, score in item["SMILES"]:
                avg_score += score
            if len(item["SMILES"]) > 0:
                avg_score /= len(item["SMILES"])
            scores.append(avg_score)
        else:
            scores.append(item["Score"])
    return np.array(steps), np.array(scores)


def extract_compounds(data, position=-1):
    if len(data) == 0:
        return [], []
    if len(data) < position:
        position = -1
    smi_tuple = data[position]["SMILES"]
    smiles, scores = zip(*smi_tuple)
    return smiles, scores


def create_score_chart(data, title, x_name="Step", y_name="Average Score", text_font_size="20pt", width=600, height=600,
                       css_classes=["score_fig"]):
    x, y = extract_average_scores(data)
    y_mean = running_average(y, 50)
    score_source = ColumnDataSource(data=dict(x=x.tolist(), y=y.tolist(), y_mean=y_mean.tolist(), raw_data=data))

    tools = "pan,wheel_zoom,box_zoom,reset,save"

    plot = figure(title=title, plot_width=width,
                  plot_height=height,
                  min_border=10, toolbar_location="right", tools=tools,
                  outline_line_color="#666666")

    plot.line('x', 'y', legend='Average score', source=score_source)
    plot.line('x', 'y_mean', legend='Running average of average score', line_width=2,
              color="firebrick", source=score_source)

    plot.xaxis.axis_label = x_name
    plot.yaxis.axis_label = y_name
    plot.title.text_font_size = text_font_size
    plot.legend.location = "bottom_right"
    plot.css_classes = css_classes
    return plot, score_source


def create_2d_molecule(data, title="Generated Molecules", position=-1, width=850, height=590,
                       css_classes=["img_outside"]):
    img_fig = Div(text="", width=width, height=height)
    img_fig.css_classes = css_classes
    if position < 0:
        position = len(data) - 1
    smiles, score = extract_compounds(data, position)
    mols = []
    scores = []
    for i, smile in enumerate(smiles):
        mol = Chem.MolFromSmiles(smile)
        if mol:
            mols.append(mol)
            scores.append(str(score[i]))
            if len(mols) >= 6:
                break
    if len(mols) > 0:
        img = Draw.MolsToGridImage(mols, molsPerRow=3, legends=scores, subImgSize=(250, 250), useSVG=True)
        img = img.replace("FFFFFF", "EDEDED")
    else:
        img = ""
    img_fig.text = '<h2>' + title + ' Step: ' + str(position) + '</h2>' + '<div class="img_inside">' + img + '</div>'
    return img_fig


def create_hover_svg(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        img = Draw.MolsToGridImage([mol], molsPerRow=1, subImgSize=(70, 70), useSVG=True)
    else:
        img = ""
    return '<div class="table_img">' + img + '</div>'
