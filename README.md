# To deploy this project

The commands below assumes you will deploy this project in the us-east-1 region, if you deploy this project in a different region then replace "us-east-1" with the region used.

```
git clone git@github.com:chiwaichan/feedmyfurbabies-cdk-iot.git
cdk feedmyfurbabies-cdk-iot
cdk deploy

git remote rm origin
git remote add origin https://git-codecommit.us-east-1.amazonaws.com/v1/repos/feedmyfurbabies-cdk-iot-FeedMyFurBabiesCodeCommitRepo
git push --set-upstream origin main
```

Please visit my blog on [FeedMyFurBabies - AWS IoT Core deployed using AWS CDK](https://chiwaichan.co.nz/2024/02/02/feedmyfurbabies-i-am-switching-to-aws-cdk/) and [other Github Repository](https://github.com/chiwaichan/aws-iot-cat-feeder) for an in-depth explanation of the architecture deployed in this project.  