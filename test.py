import torch
import os
import numpy as np
from matplotlib import pyplot as plt
from tqdm import tqdm
from cv2 import cv2
import torch.nn.functional as F

from datasets.crowd import Crowd, Crowd_sh
from models.vgg import vgg19
import argparse

args = None
th = 0.05
locate = True


# def train_collate(batch):
#     transposed_batch = list(zip(*batch))
#     images = torch.stack(transposed_batch[0], 0)
#     points = transposed_batch[1]  # the number of points is not fixed, keep it as a list of tensor
#     targets = transposed_batch[2]
#     st_sizes = torch.FloatTensor(transposed_batch[3])
#     return images, points, targets, st_sizes


def parse_args():
    parser = argparse.ArgumentParser(description='Test ')
    parser.add_argument('--data_dir', default='/home/icml007/Nightmare4214/datasets/ShanghaiTech_Crowd_Counting_Dataset-Train-Val-Test/part_B',
                        help='training data directory')
    parser.add_argument('--save_dir',
                        default='/home/icml007/Nightmare4214/PyTorch_model/UOT_shanghai_B/max_epoch_1000_crop_size_512_extra_aug_True_downsample_ratio_8_lr_1e-05_scheduler_poly_cost_p_norm_scale_0.6_blur_0.01_scaling_0.5_p_1_rho_1_rho2_None_tl_iter_2000_p_norm_2.0_norm_coord_1_phi_KL_reg_entropy_lambda_reg_1.0_batch_size_1_0112-214246/best_val.pth',
                        help='model path')
    parser.add_argument('--dataset', default='qnrf', help='dataset name: qnrf, nwpu, sha, shb')
    parser.add_argument('--device', default='0', help='assign device')
    parser.add_argument('--locate', default=False, required=False, action='store_true', help='locate crowd')
    parser.add_argument('--p_norm', type=float, default=2,
                        help='p_norm')  # ?
    parser.add_argument('--crop_size', type=int, default=512,
                        help='the crop size of the train image')
    args = parser.parse_args()
    if args.dataset.lower() == 'qnrf':
        args.crop_size = 512
    elif args.dataset.lower() == 'nwpu':
        args.crop_size = 384
        args.val_epoch = 50
    elif args.dataset.lower() == 'sha':
        args.crop_size = 256
    elif args.dataset.lower() == 'shb':
        args.crop_size = 512
    else:
        raise NotImplementedError
    return args


def get_dataloader_by_args(args):
    if args.dataset.lower() == 'qnrf':
        datasets = Crowd(os.path.join(args.data_dir, 'test'), args.crop_size, 8, is_gray=False, method='val')
    elif args.dataset.lower() in ['sha', 'shb']:
        datasets = Crowd_sh(os.path.join(args.data_dir, 'test'), args.crop_size, 8, method='val')
    else:
        raise NotImplementedError
    return torch.utils.data.DataLoader(datasets, 1, shuffle=False,
                                       num_workers=0, pin_memory=False)

def do_test(model, device, dataloader, data_dir, save_dir, locate=True, **kwargs):
    epoch_minus = []
    if os.path.isdir(save_dir):
        model_dir = save_dir
    else:
        model_dir = os.path.dirname(save_dir)
    if locate:
        locate_dir = os.path.join(model_dir, 'predict')
        os.makedirs(locate_dir, exist_ok=True)

    with torch.no_grad():
        model.eval()
        for inputs, count, name in tqdm(dataloader):
            inputs = inputs.to(device)
            assert inputs.size(0) == 1, 'the batch size should equal to 1'
            outputs = model(inputs)
            # plt.imshow(outputs.squeeze().cpu(), cmap='jet')
            # plt.show()
            temp_minu = count.shape[1] - torch.sum(outputs).item()
            # print(name, temp_minu, len(count[0]), torch.sum(outputs).item())
            epoch_minus.append(temp_minu)

            if locate:
                name = name[0] + '.jpg'

                prob_outputs = F.interpolate(outputs, scale_factor=8, mode='bilinear')
                maxpool_output = F.max_pool2d(prob_outputs, 3, 1, 1)
                maxpool_output = torch.eq(maxpool_output, prob_outputs)
                maxpool_output = maxpool_output * prob_outputs
                maxpool_output = maxpool_output.squeeze().detach().cpu().numpy()
                maxpool_output[maxpool_output < th] = 0
                y, x = maxpool_output.nonzero()
                img = cv2.imread(os.path.join(data_dir, 'test', name))
                for i, j in zip(y, x):
                    img = cv2.circle(img, (j, i), 3, (0, 0, 255), thickness=-1, lineType=cv2.LINE_AA)
                cv2.imwrite(os.path.join(locate_dir, name), img)
            del inputs
            del outputs
            torch.cuda.empty_cache()

    epoch_minus = np.array(epoch_minus)
    mse = np.sqrt(np.mean(np.square(epoch_minus)))
    mae = np.mean(np.abs(epoch_minus))
    log_str = 'Final Test: mae {}, mse {}'.format(mae, mse)
    print(log_str)
    with open(os.path.join(model_dir, 'predict.log'), 'w') as f:
        f.write(log_str + '\n')
    return mae, mse

if __name__ == '__main__':
    args = parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = args.device.strip()  # set vis gpu
    
    dataloader = get_dataloader_by_args(args)

    model = vgg19()
    device = torch.device('cuda')
    model = model.to(device)
    model.load_state_dict(torch.load(os.path.join(args.save_dir), device))
    do_test(model, device, dataloader, args.data_dir, args.save_dir, locate=True)
    
