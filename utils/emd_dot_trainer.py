import inspect
import logging
import os
import random
import time

import numpy as np
import torch
from tensorboardX import SummaryWriter
from timm.utils import AverageMeter
from torch import optim
from torch.optim.lr_scheduler import LinearLR, PolynomialLR
from torch.utils.data import DataLoader
from torch.utils.data.dataloader import default_collate
from tqdm import tqdm
import wandb

from datasets.crowd import Crowd, Crowd_sh
from geomloss import SamplesLoss
from models.vgg import vgg19
from test import do_test, get_dataloader_by_args
from utils.cost_functions import ExpCost, PerCost, L2_DIS, PNormCost
from utils.helper import Save_Handle
from utils.pytorch_utils import seed_worker, setup_seed
from utils.trainer import Trainer

print(inspect.getfile(SamplesLoss))

use_cuda = torch.cuda.is_available()
dtype = torch.cuda.FloatTensor if use_cuda else torch.FloatTensor


def grid(H, W, stride):
    coodx = torch.arange(0, W, step=stride) + stride / 2  # [0, w)
    coody = torch.arange(0, H, step=stride) + stride / 2  # [0, h)
    y, x = torch.meshgrid([coody.type(dtype) / 1, coodx.type(dtype) / 1], indexing='ij')  # (h_i, w_i)
    return torch.stack((x, y), dim=2).view(-1, 2)  # (w_i, h_i)


def train_collate(batch):
    transposed_batch = list(zip(*batch))
    images = torch.stack(transposed_batch[0], 0)
    points = transposed_batch[1]  # the number of points is not fixed, keep it as a list of tensor
    targets = transposed_batch[2]
    st_sizes = torch.FloatTensor(transposed_batch[3])
    return images, points, targets, st_sizes


class EMDTrainer(Trainer):
    def setup(self):
        """initial the datasets, model, loss and optimizer"""
        args = self.args
        if args.randomless:
            seed = args.seed
            g = torch.Generator()
            g.manual_seed(seed)
            setup_seed(seed)
        else:
            torch.backends.cudnn.benchmark = True

        global scale
        scale = args.scale
        # os.environ["WANDB_MODE"] = "offline"
        if args.cost == 'exp':
            self.cost = ExpCost(args.scale)
        elif args.cost == 'per':
            self.cost = PerCost()
        elif args.cost == 'l2':
            self.cost = L2_DIS()
        elif args.cost == 'p_norm':
            self.cost = PNormCost(args.p_norm)


        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            self.device_count = torch.cuda.device_count()
            # for code conciseness, we release the single gpu version
            assert self.device_count == 1
            logging.info('using {} gpus'.format(self.device_count))
        else:
            raise Exception("gpu is not available")

        self.downsample_ratio = args.downsample_ratio
        if args.dataset == 'qnrf':
            self.datasets = {x: Crowd(os.path.join(args.data_dir, x),
                                      args.crop_size,
                                      args.downsample_ratio,
                                      args.is_gray, x, extra_aug=args.extra_aug
                                      ) for x in ['train', 'val']}
        elif args.dataset in ['sha', 'shb']:
            self.datasets = {x: Crowd_sh(os.path.join(args.data_dir, x),
                                         args.crop_size,
                                         args.downsample_ratio,
                                         x, extra_aug=args.extra_aug
                                         ) for x in ['train', 'val']}
        else:
            raise NotImplementedError
        self.dataloaders = {x: DataLoader(self.datasets[x],
                                          collate_fn=(train_collate
                                                      if x == 'train' else default_collate),
                                          batch_size=(self.args.batch_size
                                                      if x == 'train' else 1),
                                          shuffle=(True if x == 'train' else False),
                                          num_workers=(2 if x == 'train' else 0),
                                          pin_memory=(True if x == 'train' else False), drop_last=True,
                                          worker_init_fn=seed_worker if args.randomless else None, generator=g if args.randomless else None)
                            for x in ['train', 'val']}

        self.model = vgg19()

        self.model.to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
        if args.scheduler.lower() == 'linear':
            self.scheduler = LinearLR(self.optimizer, start_factor=0.1, total_iters=10)
        elif args.scheduler.lower() == 'poly':
            self.scheduler = PolynomialLR(self.optimizer, total_iters=args.max_epoch, power=0.9)
        else:
            self.scheduler = None
        self.start_epoch = 0
        self.best_mae = {}
        self.best_mse = {}
        self.best_epoch = {}
        for stage in ['train', 'val']:
            self.best_mae[stage] = np.inf
            self.best_mse[stage] = np.inf
            self.best_epoch[stage] = 0
        self.wandb_id = None
        if args.resume:
            suf = os.path.splitext(args.resume)[-1]
            if suf == '.tar':
                checkpoint = torch.load(args.resume, self.device)
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                self.start_epoch = checkpoint['epoch'] + 1
                if self.scheduler is not None and 'scheduler' in checkpoint and checkpoint['scheduler'] is not None:
                    self.scheduler.load_state_dict(checkpoint['scheduler'])
                self.best_mae = checkpoint['best_mae']
                self.best_mse = checkpoint['best_mse']
                self.best_epoch = checkpoint['best_epoch']
                if 'wandb_id' in checkpoint:
                    self.wandb_id = checkpoint['wandb_id']
                if args.randomless:
                    random.setstate(checkpoint['random_state'])
                    np.random.set_state(checkpoint['np_random_state'])
                    torch.random.set_rng_state(checkpoint['torch_random_state'].cpu())
            elif suf == '.pth':
                self.model.load_state_dict(torch.load(args.resume, self.device))
        self.blur = args.blur
        self.criterion = SamplesLoss(blur=args.blur, scaling=args.scaling, debias=False, backend='tensorized',
                                     cost=self.cost, reach=args.reach, p=args.p)

        # self.log_dir = os.path.join('./runs', os.path.basename(args.save_dir))
        self.log_dir = os.path.join(self.save_dir, 'runs')
        # self.writer = SummaryWriter(self.log_dir)

        self.save_list = Save_Handle(max_num=args.max_model_num)
        wandb.init(
            # set the wandb project where this run will be logged
            project="GeneralizedLoss-Counting",
            id = self.wandb_id,
            name = os.path.basename(self.args.save_dir),
            # track hyperparameters and run metadata
            config=args,
            resume=True if args.resume else None,
            # sync_tensorboard=True
        )
        self.wandb_id = wandb.run.id

    def train(self):
        """training process"""
        args = self.args
        for epoch in range(self.start_epoch, args.max_epoch):
            logging.info('-' * 5 + 'Epoch {}/{}'.format(epoch, args.max_epoch - 1) + '-' * 5)
            self.epoch = epoch
            self.train_epoch(epoch)
            if epoch % args.val_epoch == 0 and epoch >= args.val_start:
                self.val_epoch(stage='val')
        self.val_epoch(stage='val')

    def train_epoch(self, epoch=0):
        epoch_loss = AverageMeter()
        epoch_mae = AverageMeter()
        epoch_mse = AverageMeter()
        epoch_start = time.time()
        self.model.train()  # Set model to training mode
        # shape = (1, int(512 / self.args.downsample_ratio), int(512 / self.args.downsample_ratio))

        # if epoch < 10:
        #     for param_group in self.optimizer.param_groups:
        #         if param_group['lr'] >= 0.1 * self.args.lr:
        #             param_group['lr'] = self.args.lr * (epoch + 1) / 10
        print('learning rate: {}, batch size: {}'.format(self.optimizer.param_groups[0]['lr'], self.args.batch_size))
        for step, (inputs, points, targets, st_sizes) in enumerate(tqdm(self.dataloaders['train'])):
            inputs = inputs.to(self.device)
            # st_sizes = st_sizes.to(self.device)
            gd_count = np.array([p.shape[0] for p in points], dtype=np.float32)
            points = [p.to(self.device) for p in points]
            # targets = [t.to(self.device) for t in targets]
            shape = (inputs.shape[0], int(inputs.shape[2] / self.args.downsample_ratio),
                     int(inputs.shape[3] / self.args.downsample_ratio))

            outputs = self.model(inputs)

            i = 0
            emd_loss = 0
            point_loss = 0
            pixel_loss = 0
            entropy = 0
            for p in points:  # (0, crop_size)
                if p.shape[0] < 1:
                    gt = torch.zeros((1, shape[1], shape[2])).cuda()
                    point_loss += torch.abs(gt.sum() - outputs[i].sum()) / shape[0]
                    pixel_loss += torch.abs(gt.sum() - outputs[i].sum()) / shape[0]
                    emd_loss += torch.abs(gt.sum() - outputs[i].sum()) / shape[0]
                else:
                    cood_grid = grid(outputs.shape[2], outputs.shape[3], 1).unsqueeze(
                        0) * self.args.downsample_ratio + (
                                        self.args.downsample_ratio / 2)
                    cood_grid = cood_grid.type(torch.cuda.FloatTensor) / float(self.args.crop_size)  # (0, 1)
                    gt = torch.ones((1, p.shape[0], 1)).cuda()
                    cood_points = p.reshape(1, -1, 2) / float(self.args.crop_size)
                    A = outputs[i].reshape(1, -1, 1)
                    l, F, G = self.criterion(A, cood_grid, gt, cood_points)  # l (1,) F(1, 4096, 1), G(1, 26, 1)

                    C = self.cost(cood_grid, cood_points)
                    PI = torch.exp((F.repeat(1, 1, C.shape[2]) + G.permute(0, 2, 1).repeat(1, C.shape[1],
                                                                                           1) - C).detach() / self.args.blur ** self.args.p) * A * gt.permute(
                        0, 2, 1)
                    entropy += torch.mean((1e-20 + PI) * torch.log(1e-20 + PI))
                    # AE = PI
                    # AE = AE.sum(1).reshape(1, -1, 1)
                    emd_loss += (torch.mean(l) / shape[0])
                    if self.args.d_point == 'l1':
                        point_loss += torch.sum(torch.abs(PI.sum(1).reshape(1, -1, 1) - gt)) / shape[0]
                    else:
                        point_loss += torch.sum((PI.sum(1).reshape(1, -1, 1) - gt) ** 2) / shape[0]
                    if self.args.d_pixel == 'l1':
                        pixel_loss += torch.sum(torch.abs(PI.sum(2).reshape(1, -1, 1).detach() - A)) / shape[0]
                    else:
                        pixel_loss += torch.sum((PI.sum(2).reshape(1, -1, 1).detach() - A) ** 2) / shape[0]
                i += 1

            loss = emd_loss + self.args.tau * (pixel_loss + point_loss) + self.blur * entropy

            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            N = inputs.size(0)
            outputs = torch.mean(outputs, dim=1)
            pre_count = torch.sum(outputs[-1]).detach().cpu().numpy()
            res = (pre_count - gd_count[-1])  # gd_count
            # if step % 200 == 0:
            #     print(res, pre_count, gd_count[-1], point_loss.item(), pixel_loss.item(), loss.item())
            epoch_loss.update(loss.item(), N)
            epoch_mse.update(np.mean(res * res), N)
            epoch_mae.update(np.mean(abs(res)), N)
        
        if self.scheduler is not None:
            self.scheduler.step()
        wandb.log({
            'train/loss': epoch_loss.avg,
            'train/mae': epoch_mae.avg,
            'train/mse': np.sqrt(epoch_mse.avg),
        }, step=self.epoch)
        # self.writer.add_scalar('train/loss', epoch_loss.avg, self.epoch)
        # self.writer.add_scalar('train/mae', epoch_mae.avg, self.epoch)
        # self.writer.add_scalar('train/mse', np.sqrt(epoch_mse.avg), self.epoch)
        logging.info('Epoch {} Train, Loss: {:.2f}, MSE: {:.2f} MAE: {:.2f}, Cost {:.1f} sec'
                     .format(self.epoch, epoch_loss.avg, np.sqrt(epoch_mse.avg), epoch_mae.avg,
                             time.time() - epoch_start))
        model_state_dic = self.model.state_dict()
        save_path = os.path.join(self.save_dir, '{}_ckpt.tar'.format(self.epoch))
        torch.save({
            'epoch': self.epoch,
            'optimizer_state_dict': self.optimizer.state_dict(),
            'model_state_dict': model_state_dic,
            'scheduler': self.scheduler.state_dict() if self.scheduler else None,
            'best_mae': self.best_mae,
            'best_mse': self.best_mse,
            'best_epoch': self.best_epoch,
            'wandb_id': self.wandb_id,
            'random_state': random.getstate(),
            'np_random_state': np.random.get_state(),
            'torch_random_state': torch.random.get_rng_state()
        }, save_path)
        self.save_list.append(save_path)  # control the number of saved models

    def val_epoch(self, stage='val'):
        epoch_start = time.time()
        self.model.eval()  # Set model to evaluate mode
        epoch_res = []
        # epoch_fore = []
        # epoch_back = []
        # Iterate over data.
        if stage == 'val':
            dataloader = self.dataloaders['val']
        with torch.no_grad():
            for inputs, points, name in tqdm(dataloader):
                inputs = inputs.to(self.device)
                # inputs are images with different sizes
                assert inputs.size(0) == 1, 'the batch size should equal to 1 in validation mode'
                outputs = self.model(inputs)

                # points = points[0].type(torch.LongTensor)
                # res = len(points) - torch.sum(outputs).item()
                res = points.shape[1] - torch.sum(outputs).item()
                del inputs
                del outputs
                torch.cuda.empty_cache()
                epoch_res.append(res)

        epoch_res = np.array(epoch_res)
        mse = np.sqrt(np.mean(np.square(epoch_res)))
        mae = np.mean(np.abs(epoch_res))
        wandb.log({
            stage + '/mae': mae,
            stage + '/mse': mse,
        }, step=self.epoch)
        # self.writer.add_scalar(stage + '/mae', mae, self.epoch)
        # self.writer.add_scalar(stage + '/mse', mse, self.epoch)
        logging.info('{} Epoch {}, MSE: {:.2f} MAE: {:.2f}, Cost {:.1f} sec'
                     .format(stage, self.epoch, mse, mae, time.time() - epoch_start))

        model_state_dic = self.model.state_dict()

        if mae < self.best_mae[stage]:
            self.best_mse[stage] = mse
            self.best_mae[stage] = mae
            self.best_epoch[stage] = self.epoch
            logging.info("{} save best mse {:.2f} mae {:.2f} model epoch {}".format(stage,
                                                                                    self.best_mse[stage],
                                                                                    self.best_mae[stage],
                                                                                    self.epoch))
            torch.save(model_state_dic, os.path.join(self.save_dir, 'best_{}.pth').format(stage))
        # print log info
        logging.info('Val: Best Epoch {} Val, MSE: {:.2f} MAE: {:.2f}, Cost {:.1f} sec'
                     .format(self.best_epoch['val'], self.best_mse['val'], self.best_mae['val'],
                             time.time() - epoch_start))

    def test(self):
        dataloader = get_dataloader_by_args(self.args)
        self.model.load_state_dict(torch.load(os.path.join(self.args.save_dir, 'best_val.pth'), self.device))
        mae, mse = do_test(self.model, self.device, dataloader, self.args.data_dir, self.args.save_dir, locate=True)
        wandb.summary['test_mae'] = mae
        wandb.summary['test_mse'] = mse
