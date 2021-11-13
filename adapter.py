from bridge import Bridge
from PIL import Image
from PIL.Image import core as _imaging
from pathlib import Path
import requests
import io
import math
import json


class Adapter:
    activeAry_params = [
        "activeAry",
        "active_ary",
    ]  # parses json params, treats these all equally as optional inputs, assigns to fsym below - formatting for API
    tokenURI_params = [
        "URIAry",
        "tokenURIs",
    ]  # similar, assigns to tsyms for API call below
    # use this as a JSON blob of 1.tokenActive and 2.ipfs indexed by child_struct_id - assumed via API call

    def __init__(self, input):
        # begin here
        self.id = input.get("id", "1")
        self.request_data = input.get("data")
        if self.validate_request_data():
            self.bridge = Bridge()
            self.set_params()
            img_data_array = self.pull_images(self.childURIAry)
            imgs_comb = self.combine_images(img_data_array, self.activeStrings)
            self.create_request(imgs_comb)
        else:
            self.result_error("Error somewhere")

    def validate_request_data(self):
        if self.request_data is None:
            return False
        if self.request_data == {}:
            return False
        return True

    def set_params(self):
        for param in self.activeAry_params:
            self.activeStrings = self.request_data.get(param)
            if self.activeStrings is not None:
                break
        for param in self.tokenURI_params:
            self.childURIAry = self.request_data.get(param)
            if self.childURIAry is not None:
                break
        # format JSON param to array here

    # modified from create_request, just return the IPFS location as a byte response here to the node
    def create_request(self, imgs_comb: Image):
        # taken from upload_to_ipfs in local prj
        # back to byte array https://stackoverflow.com/questions/33101935/convert-pil-image-to-byte-array
        image_binary = io.BytesIO()
        imgs_comb.save(image_binary, format="PNG")  # These NFTs aren't just JPEGs
        image_binary = image_binary.getvalue()
        ipfs_url = "https://ipfs.infura.io:5001"
        endpoint = "/api/v0/add"

        try:

            response = requests.post(ipfs_url + endpoint, files={"file": image_binary})

            ipfs_hash = response.json()["Hash"]
            filename = "FAM.png"
            image_uri = f"https://ipfs.io/ipfs/{ipfs_hash}?filename={filename}"
            if image_uri == "":
                image_uri = "https://ipfs.io/ipfs/QmZJU43HUCPx5sTsMKiTJbAVDRbKWq7ceU4xmmcbdzERqt?filename=error.png"  # error if for some reason not found...
            data = response.json()
            # For use with testing EA results
            # self.result = bytes(image_uri, "utf-8") #need to return as a  (hex encoded string)
            # self.result = "0x68747470733a2f2f697066732e696f2f697066732f516d52703758444179626151534b66394258435a6e345656794d6746366b6656424342334c745742755a645259453f66696c656e616d653d7465737432697066732e706e67"
            hex_img_uri = image_uri.encode(
                "utf-8"
            ).hex()  # Got this formatting from the Large Responses CL tutorial
            self.result = f"0x{hex_img_uri}"
            data[
                "result"
            ] = (
                self.result
            )  # result gets set to the imageURI! with the rest of the IPFS response returned too
            self.result_success(data)
        except Exception as e:
            self.result_error(e)
        finally:
            self.bridge.close()

    def result_success(self, data):
        self.result = {
            "jobRunID": self.id,
            "data": data,
            "result": self.result,
            "statusCode": 200,
        }

    def result_error(self, error):
        self.result = {
            "jobRunID": self.id,
            "status": "errored",
            "error": f"There was an error: {error}",
            "statusCode": 500,
        }

    def pull_images(self, JSONimgAry):
        img_data_array = []
        for child_struct_id in range(len(JSONimgAry)):
            # this for loop goes through child tokens of a given parent to pull info about each
            # grabbing token at location "child_struct_id" in the structure array related to the mapping
            ipfs_address = JSONimgAry[child_struct_id]
            # pull ipfs image down locally to do action on
            img_data = self.pull_from_ipfs(ipfs_address)
            if img_data != 0:
                img_data_array.append(img_data)
        return img_data_array

    def combine_images(self, img_data_array, activeAry):
        # iterate through local path array to pull those images into PIL Image of the right size
        # then save combined image to ipfs
        imgs = [
            # loading png from ipfs to memory (as bytes) then reading it back into Image
            # https://stackoverflow.com/questions/18491416/pil-convert-bytearray-to-image
            Image.open(io.BytesIO(child_struct_id))
            for child_struct_id in img_data_array
        ]
        for child_struct_id in range(len(img_data_array)):
            # check nft statuses here
            child_nft_status = activeAry[child_struct_id]
            if child_nft_status == False:
                imgs[child_struct_id] = self.kill_nft_img(imgs[child_struct_id])

        # for each child token, pull image into a binary
        # pick the image which is the smallest, and resize the others to match it (can be arbitrary image shape here)
        img_tile_width = math.ceil(math.sqrt(len(imgs)))
        # print(math.floor(math.sqrt(len(imgs))))  # to height
        img_tile_height = math.ceil(len(imgs) / img_tile_width)

        widths, heights = zip(*(i.size for i in imgs))

        min_width = min(widths)
        min_height = min(heights)
        total_width = img_tile_width * min_width
        total_height = img_tile_height * min_height

        new_im = Image.new(
            "RGB", (total_width, total_height), (255, 255, 255)
        )  # initialize a white bg

        newsize = min_width, min_height
        x_offset = 0
        y_offset = 0
        img_counter = 0
        # Save the new picture
        for im in imgs:
            new_im.paste(im.resize(newsize), (x_offset, y_offset))
            x_offset += min_width
            img_counter = img_counter + 1
            if (img_counter % img_tile_width) == 0:
                # print("next row")
                y_offset += min_height
                x_offset = 0

        return new_im

    def kill_nft_img(self, original_image):
        # from https://stackoverflow.com/questions/6161219/brightening-or-darkening-images-in-pil-without-built-in-functions
        # load the original image into a pixels list as param
        pixels = original_image.getdata()
        # initialise the new image
        new_image = Image.new("RGB", original_image.size)
        new_image_list = []
        brightness_multiplier = 1.0  # for testing
        extent = 85  # in percent, an int between 0 and 100. as extent increases, img gets darker
        brightness_multiplier -= float(extent / 100)

        # for each pixel, append the brightened or darkened version to the new image list
        for pixel in pixels:
            new_pixel = (
                int(pixel[0] * brightness_multiplier),
                int(pixel[1] * brightness_multiplier),
                int(pixel[2] * brightness_multiplier),
            )

            # check the new pixel values are within rgb range
            for pixel in new_pixel:
                if pixel > 255:
                    pixel = 255
                elif pixel < 0:
                    pixel = 0

            new_image_list.append(new_pixel)

        # save the new image
        original_image.putdata(new_image_list)
        return original_image

    def pull_from_ipfs(self, ipfs_address):
        if ipfs_address.startswith("ipfs://"):
            ipfs_hash = ipfs_address.partition("ipfs://")[2]
            ipfs_address = f"https://ipfs.io/ipfs/{ipfs_hash}"
        request = requests.get(
            ipfs_address
        )  # not sure on formatting here. https://stackoverflow.com/questions/30229231/python-save-image-from-url. Postman had alternate
        # Doing some checks for various IPFS URI formatting.
        # Currently supports: ipfs://<hash> or just normal image (.png) URL or a json with either of those in "image" field
        if request.status_code == 200:
            try:
                json_object = json.loads(request.content)
            except ValueError:
                # invalid json -> is just content so return the bytes
                return request.content  # return img content
            else:
                # handle JSON
                ipfs_address = json_object[
                    "image"
                ]  # valid json, return from image field
                if ipfs_address.startswith("ipfs://"):  # handling IPFS hash syntax
                    ipfs_hash = ipfs_address.partition("ipfs://")[2]
                    ipfs_address = f"https://ipfs.io/ipfs/{ipfs_hash}"
                request = requests.get(ipfs_address)
                if request.status_code == 200:
                    return request.content  # if just normal image (.png) url
        else:
            # print("Call didnt succeed")
            return 0
