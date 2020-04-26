# Linux-Fake-Background-Webcam

A virtual webcam with a fake background.
Based on a [blog post](https://elder.dev/posts/open-source-virtual-background/)
by [Benjamen Elder](https://github.com/BenTheElder/) and modifications by
[Fufu Fang](https://github.com/fangfufu/Linux-Fake-Background-Webcam).

## Prerequisites

### v4l2loopback

Install the `v4l2loopback` kernel module and load it with the following parameters:

    sudo modprobe v4l2loopback devices=1 video_nr=20 card_label="v4l2loopback" exclusive_caps=1

`exclusive_caps` is required by some programs, e.g. Zoom and Chrome.
`video_nr` specifies which `/dev/video*` file is the v4l2loopback device.
In this repository, I assume that `/dev/video20` is the virtual webcam, and
`/dev/video0` is the physical webcam.

### docker

You need to have *docker* and *docker-compose* available.

## Configuration 

Change `docker-compose.yml` to meet your needs:

- change the device mappings if you are using diffent devices:
  ```
      fakecam:
          # ...
          devices:
              # input (webcam)
              - /dev/video0:/dev/video0
              # output (virtual webcam)
              - /dev/video20:/dev/video20
          # ...
  ```

Put your background images into folder `images`.
Because of lazyness, the settings menu currently lists jpg files only.

## Usage

 - Run and initial build containers: ``docker-compose up``
 - Stop and remove containers: ``docker-compose down``
 - In a browser open `localhost:8077` for the settings menu
