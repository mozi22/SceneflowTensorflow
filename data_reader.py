import tensorflow as tf
import numpy as np

def tf_record_input_pipeline(filenames,version='1'):

    # Create a list of filenames and pass it to a queue
    filename_queue = tf.train.string_input_producer(filenames,name='InputProducerV'+version,shuffle=False)
    # Define a reader and read the next record
    recordReader = tf.TFRecordReader(name="TfReaderV"+version)

    key, fullExample = recordReader.read(filename_queue)



    # Decode the record read by the reader
    features = tf.parse_single_example(fullExample, {
        # 'width': tf.FixedLenFeature([], tf.int64),
        # 'height': tf.FixedLenFeature([], tf.int64),
        'depth1': tf.FixedLenFeature([], tf.string),
        'depth2': tf.FixedLenFeature([], tf.string),
        'depth_change': tf.FixedLenFeature([], tf.string),
        'opt_flow': tf.FixedLenFeature([], tf.string),
        'image1': tf.FixedLenFeature([], tf.string),
        'image2': tf.FixedLenFeature([], tf.string)
    },
    name="ExampleParserV"+version)

    # Convert the image data from binary back to arrays(Tensors)

    depth1 = tf.decode_raw(features['depth1'], tf.float32)
    depth2 = tf.decode_raw(features['depth2'], tf.float32)
    depth_chng = tf.decode_raw(features['depth_change'], tf.float32)

    image1 = tf.decode_raw(features['image1'], tf.uint8)
    image2 = tf.decode_raw(features['image2'], tf.uint8)
    opt_flow = tf.decode_raw(features['opt_flow'], tf.float32)

    input_pipeline_dimensions = [216, 384]
    image1 = tf.to_float(image1)
    image2 = tf.to_float(image2)

    # reshape data to its original form
    image1 = tf.reshape(image1, [input_pipeline_dimensions[0],input_pipeline_dimensions[1], 3],name="reshape_img1")
    image2 = tf.reshape(image2, [input_pipeline_dimensions[0],input_pipeline_dimensions[1], 3],name="reshape_img2")

    depth1 = tf.reshape(depth1, [input_pipeline_dimensions[0],input_pipeline_dimensions[1]],name="reshape_disp1")
    depth2 = tf.reshape(depth2, [input_pipeline_dimensions[0],input_pipeline_dimensions[1]],name="reshape_disp2")

    label_pair = tf.reshape(opt_flow, [input_pipeline_dimensions[0],input_pipeline_dimensions[1],2],name="reshape_opt_flow")
    depth_chng = tf.reshape(depth_chng,[input_pipeline_dimensions[0],input_pipeline_dimensions[1]],name="reshape_depth_change")


    image1 = tf.divide(image1,[255])
    image2 = tf.divide(image2,[255])

    image1 = combine_depth_values(image1,depth1,2)
    image2 = combine_depth_values(image2,depth2,2)

    # extra


    # d1 = tf.expand_dims(depth1,axis=2)
    # d2 = tf.expand_dims(depth2,axis=2)

    # d_final = tf.concat([d1,d2],axis=2)

    # # depth should be added to both images before this line 

    img_pair = tf.concat([image1,image2],axis=-1)
    img_pair_swapped = tf.concat([image2,image1],axis=-1)


    # change depth to inverse depth
    # depth_chng = tf.divide(1,depth_chng)

    label_with_depth_chng = combine_depth_values(label_pair,depth_chng,2)
    label_with_depth_chng_swapped = tf.zeros(label_with_depth_chng.get_shape())

    # inputt = divide_inputs_to_patches(img_pair,8)
    # label = divide_inputs_to_patches(label_pair,3)

    # padding_input = tf.constant([[0, 0],[5, 4],[0, 0]])
    padding1 = tf.constant([[4, 4],[0, 0],[0,0]])
    # padding2 = tf.constant([[4, 4],[0,0]])


    img_pair = tf.pad(img_pair,padding1,'CONSTANT')
    labels = tf.pad(label_with_depth_chng,padding1,'CONSTANT')

    img_pair_swapped = tf.pad(img_pair_swapped,padding1,'CONSTANT')
    labels_swapped = tf.pad(label_with_depth_chng_swapped,padding1,'CONSTANT')


    img_pair_final = tf.stack([img_pair,img_pair_swapped])
    labels_final = tf.stack([labels,labels_swapped])


    # just to check how shuffle_batch and batch behaves.
    # test(img_pair,img_pair_swapped)
    return {
        'input_n': img_pair_final,
        'label_n': labels_final
        # 'input': img_pair,
        # 'label': label_pair3
    }



def test(img_pair,img_pair2):

    sess = tf.InteractiveSession()
    # img_1 = tf.constant([[[1,2],[5,6]],[[9,10],[13,14]]],dtype=tf.float32)
    # img_2 = tf.constant([[[3,4],[7,8]],[[11,12],[15,16]]],dtype=tf.float32)
    # img_3 = tf.constant([[[1,2],[5,6]],[[9,10],[13,14]]],dtype=tf.float32)
    # img_4 = tf.constant([[[3,4],[7,8]],[[11,12],[15,16]]],dtype=tf.float32)

    # img_pair = tf.concat([img_1,img_2],axis=-1)
    # img_pair2 = tf.concat([img_2,img_1],axis=-1)


    # img_pair_final2 = tf.constant([[[3,4,1,2],[7,8,5,6]],[[11,12,9,10],[15,16,13,14]]],dtype=tf.float32)

    img_pair_final = tf.stack([img_pair,img_pair2])

    labels_final = tf.constant([[[1,2,3],[4,5,6]],[[7,8,9],[10,11,12]]],dtype=tf.float32)
    labels_final = tf.zeros(labels_final.get_shape(),dtype=tf.float32)

    images, labels = tf.train.shuffle_batch(
                        [ img_pair_final , labels_final ],
                        batch_size=16,
                        capacity=100,
                        num_threads=48,
                        min_after_dequeue=1,
                        enqueue_many=False)

    images = tf.Print(images,[images[0,0,:,:,0:3]],summarize=10000,message='jalalala')
    sess.run(tf.global_variables_initializer())
    coord = tf.train.Coordinator()
    threads = tf.train.start_queue_runners(sess=sess,coord=coord)

    # print(sess.run(images[0,0,:,:,0:3]))


    coord.request_stop()
    coord.join(threads)
# combines the depth value in the image RGB values to make it an RGBD tensor.
# where the resulting tensor will have depth values in the 4th element of 3rd dimension i.e [0][0][3].
# where [x][x][0] = R, [x][x][1] = G, [x][x][2] = B, [x][x][3] = D
def combine_depth_values(image,depth,rank):
    depth = tf.expand_dims(depth,rank)
    return tf.concat([image,depth],rank)


def warp(img,flow,input_pipeline_dimensions):
    x = list(range(0,input_pipeline_dimensions[1]))
    y = list(range(0,input_pipeline_dimensions[0]))
    X, Y = tf.meshgrid(x, y)

    X = tf.cast(X,np.float32) + flow[:,:,0]
    Y = tf.cast(Y,np.float32) + flow[:,:,1]

    con = tf.stack([X,Y])
    result = tf.transpose(con,[1,2,0])
    result = tf.expand_dims(result,0)


    return tf.contrib.resampler.resampler(img[np.newaxis,:,:,:],result)


def divide_inputs_to_patches(image,last_dimension):

    
    image = tf.expand_dims(image,0)
    ksize = [1, 54, 96, 1]

    image_patches = tf.extract_image_patches(
        image, ksize, ksize, [1, 1, 1, 1], 'VALID')
    image_patches_reshaped = tf.reshape(image_patches, [-1, 54, 96, last_dimension])

    return image_patches_reshaped



def get_depth_chng_from_disparity_chng(disparity,disparity_change):

    disparity_change = tf.add(disparity,disparity_change)

    depth1 = get_depth_from_disparity(disparity)
    calcdepth = get_depth_from_disparity(disparity_change)

    return tf.subtract(depth1,calcdepth)


def get_depth_from_disparity(disparity):
    # focal_length = 35
    # baseline = 1
    # focal_length * baseline = 35

    focal_length = tf.constant([35],dtype=tf.float32)

    disp_to_depth = tf.divide(focal_length,disparity)

    return disp_to_depth