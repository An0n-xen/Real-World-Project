# Generated code


# --- Step 3:  ---
def intermediate_result_3(inputs, save_dir, save_name):
    """
    Compute the Cup-to-Disc Ratio (CDR) from the segmentation masks of the optic disc and cup.
    """
    from PIL import Image
    import numpy as np
    import os
    import json

    # Load the segmentation masks
    disc_mask_path, cup_mask_path = inputs
    disc_mask = np.array(Image.open(disc_mask_path).convert('L'))
    cup_mask = np.array(Image.open(cup_mask_path).convert('L'))

    # Compute areas
    disc_area = np.sum(disc_mask == 255)
    cup_area = np.sum(cup_mask == 255)

    # Compute CDR
    cdr = cup_area / disc_area

    # Save the result to a JSON file
    result_path = os.path.join(save_dir, save_name)
    if os.path.exists(result_path):
        with open(result_path, 'r') as f:
            result = json.load(f)
    else:
        result = {}

    result['step_3'] = {'cdr': cdr}

    with open(result_path, 'w') as f:
        json.dump(result, f)
