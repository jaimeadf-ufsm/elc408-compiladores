import slugify
import ruamel.yaml

with open("automations_homi.yaml", "r") as f:
    yaml = ruamel.yaml.YAML()
    data = yaml.load(f)
    
    for item in data:
        name = slugify.slugify(item["alias"])
        with open(f"automations/{name}.yaml", "w") as f:
            yaml.dump([item], f)
    