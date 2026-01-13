import re

def mask_phone(value):
    v = re.sub(r'\D', '', value)
    if len(v) > 11: v = v[:11]
    
    if len(v) > 10:
        # Cell: (11) 91234-5678
        return re.sub(r'^(\d\d)(\d{5})(\d{4}).*', r'(\1) \2-\3', v)
    elif len(v) > 5:
        return re.sub(r'^(\d\d)(\d{4})(\d{0,4}).*', r'(\1) \2-\3', v)
    elif len(v) > 2:
        return re.sub(r'^(\d\d)(\d{0,5}).*', r'(\1) \2', v)
    else:
        return re.sub(r'^(\d*)', r'(\1', v)

def mask_cnpj(value):
    v = re.sub(r'\D', '', value)
    if len(v) > 14: v = v[:14]
    
    # Simple simulation of cumulative replaces
    # In JS: 
    # v = v.replace(/^(\d{2})(\d)/, "$1.$2");
    # v = v.replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3");
    # v = v.replace(/\.(\d{3})(\d)/, ".$1/$2");
    # v = v.replace(/(\d{4})(\d)/, "$1-$2");
    
    # Python equivalent for final state of full string
    if len(v) == 14:
        return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"
    return v # Validation mostly cares about full string

def test():
    phones = [
        "11987654321", # Cell
        "1133334444",  # Landline
        "11987"        # Partial
    ]
    
    print("--- Testing Phone Logic (JS Simulation) ---")
    for p in phones:
        print(f"Input: {p} -> Masked: {mask_phone(p)}")
        
    print("\n--- Testing CNPJ Logic ---")
    cnpjs = ["12345678000199"]
    for c in cnpjs:
        print(f"Input: {c} -> Masked: {mask_cnpj(c)}")

if __name__ == "__main__":
    test()
