import os


def read_output_log(req_path="/home/kdmz924/REINVENT/logs/run_2018-01-22-14_51_10"):
    abs_path = os.path.join(req_path, "output.log")
    content = ['']
    with open(abs_path, 'r') as f:
        content = f.readlines()
    step = None
    score = None
    agent = False
    smiles = []
    structuredcontent = []
    for line in content:
        line = line.rstrip().lstrip()
        if line.startswith("Step"):
            if len(smiles) > 0:
                structuredcontent.append({"Step": step, "Score": score, "SMILES": smiles})
                step = None
                score = None
                agent = False
                smiles = []
            linesplit = line.split()
            step = int(linesplit[1])
            score = float(linesplit[7]) if linesplit[6] == "Score:" else None
        elif line.startswith("Agent"):  # We skip the header line
            agent = True
        elif step is not None and agent:
            linesplit = line.split()
            if len(linesplit) == 5:
                _, _, _, smi_score, smi = linesplit
                smiles.append((smi, float(smi_score)))
    return structuredcontent
