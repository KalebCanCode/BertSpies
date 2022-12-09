from two_channel_nn import TwoChanNN 
import argparse
import torch
import time
from preprocess import training_loader, val_loader, word2idx, dataset, convert_img, process_words, answer_space
from torchvision import models
from torchsummary import summary
from metrics import in_batch_wup_measure
import numpy as np



def parse_args(args=None):
    """ 
    Perform command-line argument parsing (other otherwise parse arguments with defaults). 
    To parse in an interative context (i.e. in notebook), add required arguments.
    These will go into args and will generate a list that can be passed in.
    For example: 
        parse_args('--type', 'rnn', ...)
    """
    parser = argparse.ArgumentParser(description="Let's Do this Two Channel Thing :D", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--extractor',           required=True,         help='Feature Extractor such as VGG16')
    parser.add_argument('--task',           required=True,              choices=['train', 'inference'],  help='Task to run')
    parser.add_argument('--feat_size', required=True,     type=int,                   help='Feature size  of extractor')
    parser.add_argument('--device',  required=True,    type=str,                   help='Device Using')
    # parser.add_argument('--data',           required=True,              help='File path to the assignment data file.')
    parser.add_argument('--epochs',         type=int,   default=10,      help='Number of epochs')
    parser.add_argument('--lstm_units',     type=int, default=512,      help='Hidden Size of lstm')
    
    
    # parser.add_argument('--optimizer',      type=str,   default='adam', choices=['adam', 'rmsprop', 'sgd'], help='Model\'s optimizer')
    # parser.add_argument('--batch_size',     type=int,   default=100,    help='Model\'s batch size.')
    # parser.add_argument('--hidden_size',    type=int,   default=256,    help='Hidden size used to instantiate the model.')
    # parser.add_argument('--window_size',    type=int,   default=20,     help='Window size of text entries.')
    # parser.add_argument('--chkpt_path',     default='',                 help='where the model checkpoint is')
    # parser.add_argument('--check_valid',    default=True,               action="store_true",  help='if training, also print validation after each epoch')
    if args is None: 
        return parser.parse_args()      ## For calling through command line
    return parser.parse_args(args)


def train(model, optimizer, loss_fn, train_loader, val_loader, epochs, device):
    #summary(model)
    print('train() called: model=%s, opt=%s(lr=%f), epochs=%d, device=%s\n' % \
          (type(model).__name__, type(optimizer).__name__,
           optimizer.param_groups[0]['lr'], epochs, device))

    history = {} # Collects per-epoch loss and acc like Keras' fit().
    history['loss'] = []
    history['val_loss'] = []
    history['acc'] = []
    history['val_acc'] = []
    history['wups'] = []
    history['val_wups'] = []

    start_time_sec = time.time()

    for epoch in range(1, epochs+1):

        # --- TRAIN AND EVALUATE ON TRAINING SET -----------------------------
        model.train()
        train_loss         = 0.0
        num_train_correct  = 0
        num_train_examples = 0
        

        # get vocab first 
        avg_wups = []
        for batch in train_loader: 
            #print(batch)
            #print(batch)
            optimizer.zero_grad()
            #print(batch['q_tensor'][0].size(), batch['image_id'][0].size(), batch['label'])
            q_feats    = torch.stack(batch['q_tensor'], axis = 0).to(device)
            img_feats    = torch.stack(batch['image_id'], axis = 0).to(device)
            labels = torch.tensor(batch['label']).to(device)
            #print(q_feats.size(), img_feats.size(), labels.size())
            yhat = model((img_feats, q_feats))
            loss = loss_fn(yhat, labels)

            loss.backward()
            optimizer.step()

            train_loss         += loss.item() * q_feats.size(0)
            #print(torch.max(yhat, 1)[1])
            #print(labels)
            num_train_correct  += (torch.argmax(yhat, 1) == labels).sum().item()
            num_train_examples += 4
            #print(num_train_correct)
            

            yhat_list = torch.argmax(yhat,1).tolist()
            label_list = batch['label']
            wups = in_batch_wup_measure(label_list, yhat_list)
            avg_wups.append(wups)
            

        print("done")
        print(num_train_correct)
        train_acc   = num_train_correct / num_train_examples
        train_loss  = train_loss / num_train_examples
        a = np.concatenate(avg_wups).flatten()
        avg_wups = np.mean(a)
        

        
        


        # --- EVALUATE ON VALIDATION SET -------------------------------------
        model.eval()
        val_loss       = 0.0
        num_val_correct  = 0
        num_val_examples = 0
        val_wups = []

        for batch in val_loader:
            q_feats    = torch.stack(batch['q_tensor'], axis = 0).to(device)
            img_feats    = torch.stack(batch['image_id'], axis = 0).to(device)
            labels = torch.tensor(batch['label']).to(device)
            yhat = model((img_feats, q_feats))
            loss = loss_fn(yhat, labels)

            val_loss         += loss.data.item() * q_feats.size(0)
            num_val_correct  += (torch.argmax(yhat, 1) == labels).sum().item()
            num_val_examples += 4

            yhat_list = torch.argmax(yhat,1).tolist()
            label_list = batch['label']
            vwups = in_batch_wup_measure(label_list, yhat_list)
            val_wups.append(vwups)
            

        val_acc  = num_val_correct / num_val_examples
        val_loss = val_loss / num_val_examples
        v = np.concatenate(val_wups).flatten()
        val_wups = np.mean(v)


        if epoch % 1 ==0:
          print('Epoch %3d/%3d, train loss: %5.2f, train acc: %5.2f, train wups:%5.2f, val wups:%5.2f, val loss: %5.2f, val acc: %5.2f' % \
                (epoch, epochs, train_loss, train_acc, avg_wups, val_wups, val_loss, val_acc))

        history['loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['acc'].append(train_acc)
        history['val_acc'].append(val_acc)
        history['wups'].append(avg_wups)
        history['val_wups'].append(val_wups)

    # END OF TRAINING LOOP


    end_time_sec       = time.time()
    total_time_sec     = end_time_sec - start_time_sec
    time_per_epoch_sec = total_time_sec / epochs
    print()
    print('Time total:     %5.2f sec' % (total_time_sec))
    print('Time per epoch: %5.2f sec' % (time_per_epoch_sec))

    return history, model

# def main(args):
#     model = TwoChanNN(args.extractor, args.lstm_units, args.feat_size, len(word2idx))
#     optimizer = torch.optim.Adam(model.parameters(), lr = 0.001)
#     loss = torch.nn.CrossEntropyLoss()

#     # maybe need this?
#     #training_loader = torch.utils.data.DataLoader(dataset['train'], batch_size=4, shuffle=True, num_workers=2)
#     #validation_loader = torch.utils.data.DataLoader(dataset['test'], batch_size=4, shuffle=False, num_workers=2)

#     if args.task == 'train':
#         print('train')
#         #word2idx, vocab_size, train_q, test_q  = process_words()
#         history = train(model, training_loader, val_loader, args.device)
#         print(history)
    
#     if args.task == 'inference':
#         return None
import torchvision.models as models
#device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_ft = models.vgg16(pretrained=True)    
model_ft.to('cuda')
model = TwoChanNN(model_ft, 512, 4096, len(word2idx))
model.to('cuda')
print('asdfkljaskf')
optimizer = torch.optim.Adam(model.parameters(), lr = 0.001)
loss = torch.nn.CrossEntropyLoss()
history, model = train(model, optimizer, loss, training_loader, val_loader, 10, 'cuda')


def model_inference(model, image_id, question):

    #process image
    im = convert_img(img_id=image_id).to('cuda')
    im1 = torch.unsqueeze(im, dim=0)
    q = process_words(word2idx, question).to("cuda")
    q1 = torch.unsqueeze(q, dim=0)

    output = model((im1,q1))
    preds = torch.argmax(output,1)

    return answer_space[preds]


print(model_inference(model, 'image1020', 'how many pillows are there'))













    # for batch_ndx, sample in enumerate(val_loader):
    # #sample = collator(dataset['test'][2000:2010])
    #     img_feat = sample['image_id'].to('cuda')
    #     text_feat = sample['q_tensor'].to('cuda')
    #     labels = sample['label'].to('cuda')
    #     # put in evaluation mode
    #     model.eval() 
    #     # forward pass
    #     output = model((img_feat, text_feat))
    #     preds = torch.max(output,1)[1]


    #     preds = output['logits'].argmax(axis = -1).cpu().numpy() 
    #     for i in range(2000, 2010):
    #         print("$$$$$$$$$$$$$$$$$$$$$$$$$$$")
    #         showImage(i)
    #         print("Prediction:\t", answer_space[preds[i-2000]])
    #         print("$$$$$$$$$$$$$$$$$$$$$$$$$$$")
