import slugify
import ruamel.yaml

with open("automations_homi.yaml", "r") as f:
    yaml = ruamel.yaml.YAML()
    data = yaml.load(f)
    
    for i, item in enumerate(data):
        name = slugify.slugify(item["alias"])
        with open(f"automations/{i:02}-{name}.yaml", "w") as f:
            yaml.dump([item], f)
    