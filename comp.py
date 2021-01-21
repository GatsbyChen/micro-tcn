import os
import sys
import glob
import time
import torch
import argparse
import torchaudio

from microtcn.tcn import TCNModel
from microtcn.lstm import LSTMModel

def load_model(model_dir, model_id, gpu=False):

    checkpoint_path = glob.glob(os.path.join(model_dir,
                                            model_id,
                                            "lightning_logs",
                                            "version_0",
                                            "checkpoints",
                                            "*"))[0]

    hparams_file = os.path.join(model_dir, "hparams.yaml")
    batch_size = int(os.path.basename(model_id).split('-')[-1][2:])
    model_type = os.path.basename(model_id).split('-')[1]
    epoch = int(os.path.basename(checkpoint_path).split('-')[0].split('=')[-1])

    map_location = "cuda:0" if gpu else "cpu"

    if model_type == "LSTM":
        model = LSTMModel.load_from_checkpoint(
            checkpoint_path=checkpoint_path,
            map_location=map_location
        )

    else:
        model = TCNModel.load_from_checkpoint(
            checkpoint_path=checkpoint_path,
            map_location=map_location
        )

    return model

def get_files(input):
    if input is not None:
        if os.path.isdir(input):
            inputfiles = glob.glob(os.path.join(input, "*"))
        elif os.path.isfile(input):
            inputfiles = [input]
        else:
            raise RuntimeError(f" '{args.input}' is not a valid file!")

    print(f"Found {len(inputfiles)} input file(s).")

    return inputfiles

def process(inputfile, limit, threshold, gpu=False, verbose=False):
    input, sr = torchaudio.load(args.input)

    # check if the input is mono
    if input.size(0) > 1:
        print(f"Warning: Model only supports mono audio, will downmix {input.size(0)} channels.")
        input = torch.sum(input, dim=0)

    # we will resample here if needed
    if sr != 44100:
        print(f"Warning: Model only operates at 44.1 kHz, will resample from {sr} Hz.")

    # construct conditioning
    params = torch.tensor([limit, threshold])

    # add batch dimension
    input = input.view(1,1,-1)
    params = params.view(1,1,2)

    # move to GPU
    if gpu:
        input = input.to("cuda:0")
        params = params.to("cuda:0")
        model.to("cuda:0")

    # pass through model
    tic = time.perf_counter()
    out = model(input, params).squeeze()
    toc = time.perf_counter()
    elapsed = toc - tic

    if verbose:
        duration = input.size(-1)/44100
        print(f"Processed {duration:0.2f} sec in {elapsed:0.3f} sec => {duration/elapsed:0.1f}x real-time\n")

    # save output to disk (in same location)
    srcpath = os.path.dirname(inputfile)
    srcbasename = os.path.basename(inputfile).split(".")[0]
    outfile = os.path.join(srcpath, srcbasename)
    outfile += f"_limit={limit:1.0f}_thresh={threshold:0.1f}.wav"
    torchaudio.save(outfile, out.cpu(), 44100)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    # --- Input/output control
    parser.add_argument("-i", "--input", help="Path to file or folder of files to process.", type=str, default=None)
    # --- Model settings
    parser.add_argument('--model_dir', help="Path to the pre-trained model.", type=str, default='./lightning_logs/bulk')
    parser.add_argument('--model_id', help="Model id. e.g.'1-uTCN-300__causal__4-10-13__fraction-0.01-bs32'", type=str, 
                                      default='1-uTCN-300__causal__4-10-13__fraction-0.01-bs32')
    parser.add_argument('--list_models', help="Print a list of the available models.", action="store_true")
    parser.add_argument('--gpu', action="store_true")
    parser.add_argument('--verbose', action="store_true")
    # -- Compressor control parameters
    parser.add_argument('--limit', help="Compressor set to 'limit' or 'compress' mode", type=int,  default=0)
    parser.add_argument('--threshold', help="Compressor threshold value from 0 to 1", type=float, default=0.5)

    args = parser.parse_args()

    if args.list_models:
        models = sorted(glob.glob(os.path.join(args.model_dir, "*")))
        print(f"Found {len(models)} models in {args.model_dir}")
        for model in models:
            print(os.path.basename(model))
        sys.exit(0)

    print()
    model = load_model(args.model_dir, args.model_id)
    inputfiles = get_files(args.input)
    for inputfile in inputfiles:
        process(inputfile, args.limit, args.threshold, gpu=args.gpu, verbose=args.verbose)

       







   