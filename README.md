# Capstone 2020 Mirror

A full pipeline in the cloud that handles mirroring a website and running post-processing tasks.
Comes as a reusable template in case we need to mirror other sites in the future.

In August 2020, the SUTD Capstone 2020 website was launched. However, poor infrastructure planning on the vendor's side had the large media files served off a single nginx instance, leading to extremely poor scalability and reliability.

This project aimed to create a full pipeline in the cloud that handles mirroring a website and running post-processing tasks, and then finally deploying on a Cloudfront CDN for superior scalability and reliability, **with minimal idle costs (sits comfortably within AWS Free tier, only cost is the scraping (~10cents per scrape, depending on size of website) but that can be avoided too)**.
When used on the Capstone 2020 website, it speeds up page load times **by more than 4x**.
While it was created for the Capstone 2020 website, it was generified into a generic AWS SAM template that can be reployed with different settings to create mirror of other sites.

This template works best on static sites. There are some clever hacks to emulate dynamic backend behaviour (discussed in the caveats section) but they are not used in the Capstone Mirror. 

## Deployment

The first-time setup and deployment is tedious, but you only need to do it once. Most of the heavy lifting is already done through CloudFormation.

### Pre-requisites

- An AWS Account
- A registered domain name (where you want to host the mirror)
- Basic linux knowledge + know how to launch an EC2 instance and SSH into it

### Step 1: Create a Hosted Zone in Route53

You can either host the mirror at the root of your registered domain, or as a subdomain. Either way, you will need Route53 to be your nameservers for your intended mirror domain.

Create a hosted zone, then create NS records in your original DNS provider pointing to the hosted zone's NS servers.

### Step 2: Create a SSL Certificate in AWS Certificate Manager (ACM)

ACM lets you create SSL certificates for free, but they can only be used for other AWS services like CloudFront.
**CloudFront can only use certificates in the `us-east-1` (N. Virginia) region.**

1. [Request a public certificate](https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-request-public.html) with the correct domain names. Generally, the domain names are `yourmirror.com` and `www.yourmirror.com`.
2. Select DNS validation as the preferred validation type.
3. After the request has been submitted, a button should appear that says "create these records in route53". Click that button and wait several minutes for the certificate to be validated.

### Step 3: Create an EC2 Key Pair on EC2

Refer to [AWS Documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html).
This key pair will be used on all crawler instances so you can debug/trouble by SSH-ing in later.
Remember to save the private key on your machine!

### Step 4: Create and format an EBS volume on EC2

An EBS volume is used as the cache for httrack. You will need to spin up a throwaway instance to create a filesystem on the volume. Once a filesystem is present, you can detach the volume from the instance and terminate that instance.

Refer to [AWS Documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-using-volumes.html) on how to mount the volume and create a filesystem. Skip the parts about automounting because we wont be using this instance again.

1GB is the minimum size of an EBS Volume. Most simple sites can fit within 1GB. Capstone 2020, because of the media files, is over 3GB.

### Step 5: Install the AWS CLI and AWS SAM on your machine

Go google it. Setting credentials comes in the next step.

### Step 6: Create Administrator Access Keys

First [create a separate administrator user](https://docs.aws.amazon.com/translate/latest/dg/setting-up.html) with CLI/API access, then create a set of access keys for that user.
[Configure the AWS CLI to use the access keys](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

### Step 7: Build and deploy this SAM template

In this project,

```
sam build --use-container && sam deploy --guided
```

Docker must be running.

The deploy step will prompt you with a set configuration values:

- Stack Name: something sensible, e.g. `capstone-mirror`
- Region: `ap-southeast-1` or somewhere else
- Parameters:
  - `VolumeId`: The id of the EBS volume you created in step 4. Should start with `vol-`
  - `KeyPairName`: The name of the key pair you created in step 3.
  - `CertificateArn`: The ARN of the certificate you created in step 2, can be found in the ACM console. Starts with `arn:aws:acm:us-east-1:`
  - `HostedZoneName`: The name of the hosted zone you created in step 1. It is usually your desired mirror domain with a dot at the end.
  - `MirrorTarget`: Domain of the site you want to make a copy of, e.g. `capstone.sutd.edu.sg`
  - `MirrorDomain`: Domain where your mirror will reside **without www**, e.g. `capstone.opensutd.org`
  
You can leave the default options for the other questions SAM will ask.

While the stack is deploying (can take as long as 20 minutes, you can proceed to the next step)

### Step 8: Customize the post-processing custom script

The post-processing script is located at `playbooks/post_process/python_scripts/files/process.py`.
This script is **site specific**. The one in this repo is made for Capstone 2020.

If you are mirroring other sites, you must replace the contents of the script with code that you want to execute on the mirror contents of your target website. If you have no need for this feature you can comment it out everything in the file first.

### Step 9: Upload the playbooks to S3

Wait for the stack to finish deploying (step 7). Once it is done, you should see the `PlaybooksBucketName` output value – this is the name of the bucket you need to upload the contents of the `playbooks` folder to.

Run the following command:

```
aws s3 sync playbooks/ s3://YOUR_BUCKET_NAME/ --delete
```

Where `YOUR_BUCKET_NAME` is the value of `PlaybooksBucketName`. You **must** have the trailing slash after `playbooks` or it will upload the folder itself, not the contents of the folder.

## Building the Mirror

Now we go to actually scraping the website and publishing it. There are three parts to the build process:

- Scraping the website (skippable if you already scraped it locally to avoid EC2 costs)
- Post-processing
- Publishing

The process is started by a Step Function created as part of the stack. The name of the step function, `MirrorBuildStepFunctionName` can be found in the output of the Cloudformation template (shown after `sam build`)

Go to the Step Functions Console on AWS and find the step function. Start a new execution. The input payload format is:

```json
{
    "skip_scraping": false
}
```

Where `skip_scraping` is a boolean. To do a full mirror build, set it to false. If set to true, it assumes a mirror is already present on the cache volume.

The build process will spin up a `t3a.medium` instance used for scraping and post-processing. It will automatically be terminated at the end of the mirror build process.

The console includes a graph that shows you which step it currently is at. The first scraping run can take several hours, so it's best to leave it be and come back later.

When the full execution is complete, you can try visiting your mirror at the domain you specified when doing `sam deploy --guided`.

#### Using a local mirror

If you have already scraped your target site locally via httrack, you can skip the scraping step.

You will need to upload the mirror contents (the parent directory that includes the mirror index, `hts-log.txt` etc) onto the EBS volume. You can spin up a throwaway instance, then mount and `rsync` into it, and shutdown the instance afterwards.

Then, when starting a new execution in the Step Function, set `skip_scraping` to `true`.

## Caveats & Further Discussion

#### Static & Dynamic Sites

POST and other routes meant to be used with a backend wont work. This is a static mirror, so forms and the like won't work.

You can try using Lambda@Edge to intercept these requests, and either return a mock response or forwarding them to the mirror target (i.e. the "true origin").
If you're feeling ambitious, you can reverse-engineer your target site and forwards requests to your own backend implementation.

#### Javascript content

httrack can not clone content that is rendered via Javascript, because it is a simple HTTP client.

Some components can be salvaged. For example, the Capstone 2020 website's CMS uses placeholder `<div>` tags to embed youtube videos – a Javascript function on page load transforms the `<divs>` into proper `iframes`.
A function was added in the Python post-processing script to normally convert those into `iframes`.

If the entire site is Javascript (e.g. SPAs like React and Vue), gg. You need to write your own browser-based scraper (e.g. based on selenium), then include it in the `provision` playbook to run as part of the scraping step. 