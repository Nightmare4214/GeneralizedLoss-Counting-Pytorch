import torch
import os
import numpy as np
from tqdm import tqdm

from datasets.crowd import Crowd
from models.vgg import vgg19
import argparse

args = None


def train_collate(batch):
    transposed_batch = list(zip(*batch))
    images = torch.stack(transposed_batch[0], 0)
    points = transposed_batch[1]  # the number of points is not fixed, keep it as a list of tensor
    targets = transposed_batch[2]
    st_sizes = torch.FloatTensor(transposed_batch[3])
    return images, points, targets, st_sizes


def parse_args():
    parser = argparse.ArgumentParser(description='Test ')
    parser.add_argument('--data_dir', default='/mnt/data/datasets/UCF-Train-Val-Test',
                        help='training data directory')
    parser.add_argument('--save_dir',
                        default='/mnt/data/PycharmProject/GeneralizedLoss-Counting-Pytorch/ucf_vgg19_ot_84.pth',
                        help='model path')
    parser.add_argument('--device', default='0', help='assign device')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = args.device.strip()  # set vis gpu

    datasets = Crowd(os.path.join(args.data_dir, 'test'), 512, 8, is_gray=False, method='val')
    dataloader = torch.utils.data.DataLoader(datasets, 1, shuffle=False,
                                             num_workers=1, pin_memory=False)
    model = vgg19()
    device = torch.device('cuda')
    model = model.to(device)
    model.load_state_dict(torch.load(os.path.join(args.save_dir), device))
    epoch_minus = []
    with torch.no_grad():
        for inputs, count, name in tqdm(dataloader):
            inputs = inputs.to(device)
            assert inputs.size(0) == 1, 'the batch size should equal to 1'
            outputs = model(inputs)
            temp_minu = len(count[0]) - torch.sum(outputs).item()
            # print(name, temp_minu, len(count[0]), torch.sum(outputs).item())
            epoch_minus.append(temp_minu)

    epoch_minus = np.array(epoch_minus)
    mse = np.sqrt(np.mean(np.square(epoch_minus)))
    mae = np.mean(np.abs(epoch_minus))
    log_str = 'Final Test: mae {}, mse {}'.format(mae, mse)
    print(log_str)
