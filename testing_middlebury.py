import tensorflow as tf

FLAGS = tf.app.flags.FLAGS

tf.app.flags.DEFINE_string('CKPT_FOLDER_SCGAN', '../ScGAN/ckpt/driving/cgan1_with_encoder_dropout',
                           """The name of the tower """)


tf.app.flags.DEFINE_string('CKPT_FOLDER', 'ckpt/driving/epe_all_ds/train/',
                           """The name of the tower """)

tf.app.flags.DEFINE_boolean('TEST_GAN', False,
                            """Whether to log device placement.""")

tf.app.flags.DEFINE_boolean('DRIVING', True,
                            """Whether to log device placement.""")


if FLAGS.TEST_GAN == True:
	import sys
	sys.path.insert(0, '../ScGAN')


import network
import synthetic_tf_converter as stc
import losses_helper as lhpl
import numpy as np
import helpers as hpl
import math
from PIL import Image 
import ijremote as ij
ij.setHost('tcp://linus:13463')

u_factor = 0.414814815
v_factor = 0.4

input_size = math.ceil(960 * v_factor), math.floor(540 * u_factor)


def get_depth_from_disp(disparity):
	focal_length = 1050.0
	disp_to_depth = disparity / focal_length
	return disp_to_depth

def combine_depth_values(img,depth):
	depth = np.expand_dims(depth,2)
	return np.concatenate((img,depth),axis=2)

def parse_input(img1,img2,disp1,disp2):

	img1 = Image.open(img1)
	img2 = Image.open(img2)

	img1 = img1.resize(input_size, Image.BILINEAR)
	img2 = img2.resize(input_size, Image.BILINEAR)

	if FLAGS.DRIVING == False:
		disp1 = Image.open(disp1)
		disp2 = Image.open(disp2)

		disp1 = disp1.resize(input_size, Image.NEAREST)
		disp2 = disp2.resize(input_size, Image.NEAREST)

	else:
		disp1 = hpl.readPFM(disp1)[0]
		disp2 = hpl.readPFM(disp2)[0]

		disp1 = Image.fromarray(disp1,mode='F')
		disp2 = Image.fromarray(disp2,mode='F')

		disp1 = disp1.resize(input_size, Image.NEAREST)
		disp2 = disp2.resize(input_size, Image.NEAREST)


	disp1 = np.array(disp1,dtype=np.float32)
	disp2 = np.array(disp2,dtype=np.float32)

	depth1 = get_depth_from_disp(disp1)
	depth2 = get_depth_from_disp(disp2)

	# normalize
	depth_norm = np.max(depth1)
	depth1 = depth1 / depth_norm
	depth2 = depth2 / depth_norm

	img1_orig = np.array(img1)
	img2_orig = np.array(img2)


	img1 = img1_orig / 255
	img2 = img2_orig / 255

	rgbd1 = combine_depth_values(img1,depth1)
	rgbd2 = combine_depth_values(img2,depth2)

	img_pair = np.concatenate((rgbd1,rgbd2),axis=2)

				# optical_flow
	return img_pair, disp1, img2_orig

def load_model_ckpt(sess,filename):
	saver = tf.train.Saver()
	saver.restore(sess, tf.train.latest_checkpoint(filename))

def downsample_opt_flow(data,size):

	u = data[:,:,0]
	v = data[:,:,1]
	
	dt = Image.fromarray(u)
	dt = dt.resize(size, Image.NEAREST)

	dt2 = Image.fromarray(v)
	dt2 = dt2.resize(size, Image.NEAREST)
	u = np.array(dt)
	v = np.array(dt2)

	return np.stack((u,v),axis=2)

def predict(img_pair,optical_flow):

	if FLAGS.TEST_GAN == True:
		optical_flow = downsample_opt_flow(optical_flow,(192,112))



	img_pair = np.expand_dims(img_pair,axis=0)
	optical_flow = np.expand_dims(optical_flow,axis=0)



	feed_dict = {
		X: img_pair,
		Y: optical_flow
	}

	loss, v = sess.run([loss_result,predict_flow2],feed_dict=feed_dict)

	return denormalize_flow(v), loss

def denormalize_flow(flow):

	u = flow[:,:,:,0] * input_size[0]
	v = flow[:,:,:,1] * input_size[1]
	# w = flow[:,:,2] * self.max_depth_driving_chng
	u = np.expand_dims(u,axis=-1)
	v = np.expand_dims(v,axis=-1)

	flow = np.concatenate((u,v),axis=-1)
		
	return flow

def warp(img,flow):

	img = img.astype(np.float32)

	x = list(range(0,input_size[0]))
	y = list(range(0,input_size[1]))
	X, Y = tf.meshgrid(x, y)

	X = tf.cast(X,np.float32) + flow[:,:,0]
	Y = tf.cast(Y,np.float32) + flow[:,:,1]

	con = tf.stack([X,Y])
	result = tf.transpose(con,[1,2,0])
	result = tf.expand_dims(result,0)
	return tf.contrib.resampler.resampler(img[np.newaxis,:,:,:],result)


def denormalize_flow_tensor(flow):


	u = flow[:,:,:,0] * input_size[0]
	v = flow[:,:,:,1] * input_size[1]
	# w = flow[:,:,2] * self.max_depth_driving_chng
	
	flow = tf.concat([tf.expand_dims(u,axis=-1),tf.expand_dims(v,axis=-1)],axis=3)
	

	return flow

def parse_results(img_pair, optical_flow, img2_orig):

	# optical_flow_normed = normalizeOptFlow(optical_flow,(384,224))
	predicted_flow, loss = predict(img_pair,optical_flow)

	if FLAGS.TEST_GAN == True:
		img2_to_tensor = further_resize_imgs(img2_to_tensor)
		orig_flow_to_tensor = further_resize_lbls(orig_flow_to_tensor)

	predicted_flow = np.squeeze(predicted_flow)
	# warped_img =  lhpl.flow_warp(img2_to_tensor,orig_flow_denormed_to_tensor)
	warped_img =  warp(img2_orig,predicted_flow)
	result = warped_img.eval()[0].astype(np.uint8)
	show_image(result,'warped_img_pr')


	# denorm_u,denorm_v = sess.run([predicted_flow[0,:,:,0],predicted_flow[0,:,:,1]])

	# ij.setImage('gt_flow_u',optical_flow[:,:,0])
	# ij.setImage('gt_flow_v',optical_flow[:,:,1])
	# ij.setImage('de_opt_flow_u',predicted_flow[0,:,:,0])
	# ij.setImage('de_opt_flow_v',predicted_flow[0,:,:,1])
	# ij.setImage('warped',np.transpose(warped_img2,0,1]))
	# ij.setImage('orig',np.transpose(img2_orig,[2,0,1]))

	# ij.setImage('orig',img2_orig)
	# ij.setImage('warped',warped_img)
	# Image.fromarray(np.uint8(img2_orig)).show()
	# Image.fromarray(np.uint8(warped_img)).show()
	# print(loss)

def show_image(array,img_title):
	# shaper = array.shape
	a = Image.fromarray(array)
	# a = a.resize((math.ceil(shaper[1] * 2),math.ceil(shaper[0] * 2)), Image.BILINEAR)
	a.show(title=img_title)
	# a.save('prediction_without_pc_loss.jpg')

def perform_testing_with_driving():

	dataset_root = '../dataset_synthetic/driving/'
	IMG_ROOT = 'frames_finalpass_webp/35mm_focallength/scene_backwards/fast/left/'
	DISP_ROOT = 'disparity/35mm_focallength/scene_backwards/fast/left/'
	FLOW_ROOT = 'optical_flow/35mm_focallength/scene_backwards/fast/into_future/left/'
	DISPARITY_CHNG_ROOT = 'disparity_change/35mm_focallength/scene_backwards/fast/into_future/left/'
	IMG1_NUMBER = '0001'
	IMG2_NUMBER = '0002'

	IMG1 = dataset_root + IMG_ROOT + IMG1_NUMBER + '.webp'
	IMG2 = dataset_root + IMG_ROOT + IMG2_NUMBER + '.webp'
	DISPARITY1 = dataset_root + DISP_ROOT + IMG1_NUMBER + '.pfm'
	DISPARITY2 = dataset_root + DISP_ROOT + IMG2_NUMBER + '.pfm'
	DISPARITY_CHNG = dataset_root + DISPARITY_CHNG_ROOT + IMG1_NUMBER + '.pfm'
	FLOW = dataset_root + FLOW_ROOT + 'OpticalFlowIntoFuture_' + IMG1_NUMBER + '_L.pfm'

	img_pair, optical_flow, img2_orig = parse_input(IMG1,IMG2,DISPARITY1,DISPARITY2)
	optical_flow = hpl.readPFM(FLOW)[0]
	optical_flow = downsample_opt_flow(optical_flow,(384,224))

	parse_results(img_pair, optical_flow, img2_orig)



def perform_testing_with_middlebury():
	dataset_root = '../dataset_synthetic/middlebury/'
	dataset_type = ['middlebury2003','middlebury2005']

	for typee in dataset_type:

		ds_current_root = dataset_root + typee

		if typee == dataset_type[0]:
			print('parsing middlebury 2003 ... ')
			folders = ['conesF','teddyF']

			img1_path = 'im2.ppm'
			img2_path = 'im6.ppm'
			disp1_path = 'disp2.pgm'
			disp2_path = 'disp6.pgm'

		else:
			print('parsing middlebury 2005 ... ')
			folders = ['Art','Books','Dolls','Laundry','Moebius','Reindeer']

			img1_path = 'view1.png'
			img2_path = 'view5.png'
			disp1_path = 'disp1.png'
			disp2_path = 'disp5.png'


		for folder in folders:
			final_path = ''
			final_path = ds_current_root + '/' +folder + '/'

			img1_path_final = final_path + img1_path
			img2_path_final = final_path + img2_path
			disp1_path_final = final_path + disp1_path
			disp2_path_final = final_path + disp2_path

			print('')
			print('folder = '+ folder)
			print('')

			img_pair, optical_flow, img2_orig = parse_input(img1_path_final,img2_path_final,disp1_path_final,disp2_path_final)
			flow_expanded_u = np.expand_dims(optical_flow,axis=2) 
			flow_expanded_v = np.expand_dims(np.zeros_like(optical_flow),axis=2)
			optical_flow = np.concatenate([flow_expanded_u,flow_expanded_v],axis=-1)
			parse_results(img_pair, optical_flow, img2_orig)




def normalizeOptFlow(flow,input_size):

	# remove the values bigger than the image size
	flow[:,:,0][flow[:,:,0] > input_size[0] ] = 0
	flow[:,:,1][flow[:,:,1] > input_size[1] ] = 0

	# separate the u and v values 
	flow_u = flow[:,:,0]
	flow_v = flow[:,:,1]

	# normalize the values by the image dimensions
	flow_u = flow_u / input_size[0]
	flow_v = flow_v / input_size[1]



	# combine them back and return
	return np.dstack((flow_u,flow_v))


def further_resize_imgs(network_input_images):
    network_input_images = tf.image.resize_images(network_input_images,[112,192],method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
    return network_input_images

def further_resize_lbls(network_input_labels):

	network_input_labels = tf.image.resize_images(network_input_labels,[112,192],method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)

	network_input_labels_u = network_input_labels[:,:,:,0] * 0.5
	network_input_labels_v = network_input_labels[:,:,:,1] * 0.5

	network_input_labels_u = tf.expand_dims(network_input_labels_u,axis=-1)
	network_input_labels_v = tf.expand_dims(network_input_labels_v,axis=-1)

	network_input_labels = tf.concat([network_input_labels_u,network_input_labels_v],axis=3)

	return network_input_labels


sess = tf.InteractiveSession()
X = tf.placeholder(dtype=tf.float32, shape=(1, 224, 384, 8))
Y = tf.placeholder(dtype=tf.float32, shape=(1, 224, 384, 2))

if FLAGS.TEST_GAN == True:
	predict_flow2 = network.generator(X)
	predict_flow2 = predict_flow2[1]
	Y = further_resize_lbls(Y)
else:
	predict_flow2 = network.train_network(X)
	predict_flow2 = predict_flow2[0]

predict_flow2 = predict_flow2[:,:,:,0:2] 
predict_flow2 = denormalize_flow_tensor(predict_flow2)
loss_result = lhpl.endpoint_loss(Y,predict_flow2,1)


# loss_result = tf.sqrt(tf.reduce_mean(tf.square(tf.subtract(Y, predict_flow2))))

if FLAGS.TEST_GAN == True:
	load_model_ckpt(sess,FLAGS.CKPT_FOLDER_SCGAN)
else:
	load_model_ckpt(sess,FLAGS.CKPT_FOLDER)

if FLAGS.DRIVING == True:
	perform_testing_with_driving()
else:
	perform_testing_with_middlebury()